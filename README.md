# cellprofiler-dspy-review

A small demo of using [DSPy](https://dspy.ai) to build a code reviewer
calibrated to a specific human reviewer's style, trained on that person's
own past PR comments. The reviewer here is `gnodar01`, who handles ~all
review on [CellProfiler](https://github.com/CellProfiler/CellProfiler).

## The argument this is testing

A hand-written review prompt (a SKILL.md, a CLAUDE.md section, a system
prompt) is a frozen, untyped, unevaluated artifact - silently coupled to
whichever model was strong when someone wrote it. A DSPy program is a
typed contract (the `Signature`), a metric, and a training set - which
together let an optimizer write better instructions than a human would,
and re-write them when the model swaps.

The skeptical objection is that you need labels and a metric, which is
expensive. The case where that objection collapses: a single reviewer who
is the ground truth, with their inline review comments already sitting in
the GitHub API.

## Layout

- `harvest.py` - pulls PR diffs and gnodar01's inline review comments;
  writes `data/train.json` and `data/test.json`.
- `review.py` - the DSPy program. `CodeReview` signature with structured
  `Issue` outputs, `LabeledFewShot` compile step using gnodar01's actual
  comments as demos, LLM-as-judge metric for recall.
  - `uv run python review.py baseline` - zero-shot eval on held-out PR
  - `uv run python review.py compile`  - compile, save to `compiled.json`
  - `uv run python review.py compare`  - side-by-side baseline vs compiled
- `peek.py` - quick visual inspection of predictions vs gold.

## Data

- Train: 19 PRs, 31 files with substantive gnodar01 comments, 65 comments total.
- Test (held out): PR #5104 (`measureobjectintensity` library refactor),
  3 files, 11 gold comments.

## Running

    uv sync
    export ANTHROPIC_API_KEY=...
    uv run python harvest.py
    uv run python review.py baseline
    uv run python review.py compile
    uv run python review.py compare

Defaults are configurable via env: `PROGRAM_LM`, `JUDGE_LM` (LiteLLM
model strings). Tested with `anthropic/claude-sonnet-4-6` and
`anthropic/claude-opus-4-7`.

## Results, honestly

On the held-out PR (3 files, 11 gold comments from gnodar01):

| model + program | mean recall |
|---|---|
| sonnet-4-6 baseline (zero-shot)             | 0.000 |
| sonnet-4-6 + LabeledFewShot (k=5 from gold) | 0.000 |
| opus-4-7 baseline (zero-shot)               | 0.037 |

These are the strict-judge numbers, and they understate what's actually
happening. The judge requires "same concern about the same code location"
which is a very tight bar against gnodar01's terse style ("No longer used",
"Resolve TODO"). The qualitative diff between baseline and compiled is
more informative: see `compare_out.txt` for the full side-by-side.

What you can see by eye in that file:
- Compiled is **leaner** (4-5 issues per file vs baseline's 5-7) and
  drops generic style nits (trailing whitespace, blank-line conventions).
- Compiled catches **architectural** concerns baseline misses. Example
  on `_measureobjectintensity.py`: compiled flags
  `crop_labels_and_image` being imported from `cellprofiler_core` inside
  a library module - a textbook gnodar01 layering concern. Baseline doesn't.
- **Neither** matches gnodar01's terse minimalism well. The model still
  wants to write paragraphs where gnodar01 writes "Not used."

So the strict metric reads as "no improvement," while the qualitative
output reads as "moving in the right direction but not all the way."
That gap is itself the most useful finding: the metric is the bottleneck,
not the program. Better metric (looser judge, or precision-as-well-as-recall),
better optimizer (MIPROv2 over LabeledFewShot), and labels covering more
of gnodar01's style range are all on the table.

## What's deliberately simple here

- One reviewer (gnodar01) as ground truth - by design.
- Recall-only metric. A real version would also score precision (penalize
  hallucinated issues that gnodar01 wouldn't have raised).
- `LabeledFewShot` with k=5 demos. `BootstrapFewShot` was tried first but
  it ends up using the program's own outputs as demos - which is the
  failing style we're trying to leave behind.
- Per-file framing rather than whole-PR. Smaller token budget, easier to
  label.

## What you'd build on top of this

1. Swap `LabeledFewShot` for `MIPROv2` - searches over instructions too,
   not just demo selection. With a working metric, this is where most of
   the actual lift comes from.
2. Add a precision component to the metric using an LLM-as-judge that
   asks "is this issue something gnodar01 would have raised?" - distinct
   from "does this issue match a specific gold comment?".
3. KNN-based demo selection (`KNNFewShot`) so demos are topically close
   to the test diff, not random samples.
4. Re-harvest periodically. Recompile. Diff the resulting instructions
   to see what the optimizer learned about gnodar01's style over time.
5. Wire it into a GitHub Action that posts draft-PR review comments with
   a `[bot]` prefix and an opt-out label.

## Why this is the cleanest case for DSPy

CellProfiler today has effectively one author (sspathak, ~2x commit volume)
and one reviewer (gnodar01, on nearly every reviewed PR). That means:

- Inter-rater disagreement vanishes - one person's voice is the metric.
- The labels already exist as inline review comments in the GitHub API.
- The domain is narrow (image analysis modules, stable conventions),
  which is the regime where instruction search works best.
- A single maintainer can own labels, metric, and harness end-to-end -
  the operating cost that crushes teams is fine for one person.
