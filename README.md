# cellprofiler-dspy-review

DSPy code reviewer trained on gnodar01's past CellProfiler review comments.

## Why

Code-review prompts are usually prose - frozen, untyped, model-coupled, never measured against the human they're supposed to imitate. The hypothesis: when one reviewer dominates a repo, their inline comments are a free training set, and a typed signature plus those labels should produce reviews closer to that reviewer's voice than a hand-written prompt does. The experiment compares zero-shot baseline against a `LabeledFewShot` compile on a held-out PR; success looks like compiled output that recovers gnodar01's terse, architecture-focused concerns where baseline emits generic style nits. The hypothesis is rejected if compiled is indistinguishable from baseline (output style and concern-mix), or if a hand-written prompt enumerating gnodar01's heuristics matches the compiled program - in this run the strict recall metric reads as rejection, but the qualitative diff is directional, so the result is "metric too tight, signal real but small," not a clean verdict.

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

## Beyond code review: data analysis review

The same shape - one dominant reviewer, written critiques as labels, typed signature predicting structured issues - might transfer to reviewing data analyses, where systematic review is much rarer than for code. D'Agostino McGowan, Peng, and Hicks (JCGS 2023, [Design Principles for Data Analysis](https://www.tandfonline.com/doi/full/10.1080/10618600.2022.2104290)) propose six measurable principles - data matching, exhaustive, skeptical, second-order, clarity, reproducible - on which an analysis can be scored, and a follow-up ([JDS 2024](https://jds-online.org/journal/JDS/article/1437/info)) frames a good analysis as one whose principles align with the audience's. That gives a labeling schema: a senior analyst's critiques of past analyses (margin comments on notebooks, threads on analysis PRs, written report feedback) become structured labels per principle, and the DSPy compile step produces a reviewer calibrated to that person's principle weights. The structural break from code review is that the artifact is messier (notebook + figures + narrative, not a diff), so the hard problem is *labeling consistency*, not the optimizer; the cleanest falsification is the same test as here on a different artifact - if compiled output is indistinguishable from baseline, the technique is the limit, not the labels.
