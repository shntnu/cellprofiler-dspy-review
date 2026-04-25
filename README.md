# cellprofiler-dspy-review

> [!NOTE]
> **Archived.** This trains a reviewer on inline GitHub comments. In the PRs this corpus draws from, those comments are deliberately short: each one stands in for ~30 minutes of pair-programming discussion between two engineers that never made it to GitHub. A lot of what would be a review comment in an async team is instead a fix one of them pushed directly, or something they worked out live. Mimicking the comments mimics fragments, not the review.
>
> The right corpus is a small team that does everything on GitHub - PR comments, issues, discussions, milestones, project board. Thanks to [@gnodar01](https://github.com/gnodar01) for the redirect.

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

