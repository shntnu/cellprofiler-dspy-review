# cellprofiler-dspy-review

> [!NOTE]
> **Archived.** This repo is parked. The training corpus assumed inline review comments carried the full reviewer signal, but in this codebase the comments are deliberately terse - shorthand for offline pair-programming discussions that aren't on GitHub. Mimicking the surface form would miss the rationale underneath.
>
> The viable alternative is a corpus from a strictly-async team where the GitHub artifacts are the discussion, not a pointer to it.
>
> Credit to [@gnodar01](https://github.com/gnodar01) for the diagnosis and the redirect.

DSPy code reviewer trained on gnodar01's past CellProfiler review comments.

## Hypothesis

When one reviewer dominates a repo, their inline comments are a free training set, and a typed signature with those labels produces reviews closer to that reviewer's voice than a hand-written prompt does - rejected if compiled output is indistinguishable from baseline. The same shape (one reviewer, critiques as labels) might extend to reviewing data analyses, where D'Agostino McGowan, Peng, and Hicks ([JCGS 2023](https://www.tandfonline.com/doi/full/10.1080/10618600.2022.2104290), [JDS 2024](https://jds-online.org/journal/JDS/article/1437/info)) give a labeling schema in their six design principles (data matching, exhaustive, skeptical, second-order, clarity, reproducible); the harder problem there is labeling consistency, not the optimizer.

## Run

    uv sync
    export ANTHROPIC_API_KEY=...
    uv run python harvest.py
    uv run python review.py baseline   # zero-shot eval
    uv run python review.py compile    # LabeledFewShot, save compiled.json
    uv run python review.py compare    # side-by-side on held-out PR

Override models via `PROGRAM_LM` / `JUDGE_LM` env vars.

## Data

- Train: 19 PRs, 31 files with gold, 65 comments
- Test (held out): PR #5104, 3 files, 11 comments

## Results on PR #5104

| program | mean recall |
|---|---|
| sonnet-4-6 baseline             | 0.000 |
| sonnet-4-6 + LabeledFewShot k=5 | 0.000 |
| opus-4-7 baseline               | 0.037 |

Strict-judge metric is too tight for gnodar01's terse style ("Not used.",
"Resolve TODO"). See `compare_out.txt` for the qualitative diff: compiled
is leaner and catches architectural concerns (e.g. `cellprofiler_core`
imports inside library modules) that baseline misses.

## Files

- `harvest.py` - GitHub API -> `data/{train,test}.json`
- `review.py` - signature, metric, compile/compare
- `peek.py` - debug inspection
- `compiled.json` - compiled program artifact
- `compare_out.txt` - sonnet baseline vs compiled, side by side

## Next

- `MIPROv2` (search instructions, not just demos)
- Precision in the metric (judge: "would gnodar01 raise this?")
- `KNNFewShot` for topical demos
- Wire into a draft-PR GitHub Action

