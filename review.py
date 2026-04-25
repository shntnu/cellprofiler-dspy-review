"""DSPy code-review program for CellProfiler, calibrated to gnodar01's review style.

Usage:
    uv run python review.py baseline   # zero-shot eval on test set
    uv run python review.py compile    # compile with BootstrapFewShot, save program
    uv run python review.py compare    # show baseline vs compiled on a held-out PR
"""

import json
import os
import sys
from pathlib import Path
from typing import Literal

import dspy
from pydantic import BaseModel, Field

DATA = Path("data")
ARTIFACT = Path("compiled.json")

# -------- Models --------

PROGRAM_LM = os.environ.get("PROGRAM_LM", "anthropic/claude-haiku-4-5-20251001")
JUDGE_LM = os.environ.get("JUDGE_LM", "anthropic/claude-haiku-4-5-20251001")


class Issue(BaseModel):
    category: Literal[
        "unused-code",         # gnodar01's most common: "X not used", "no longer used"
        "convention",          # imports order, TODO format, print vs logging
        "abstraction",         # use library opts, raw values vs enum, magic constants
        "correctness",
        "style",
    ] = Field(description="What kind of concern this is")
    line: int | None = Field(description="Line number in the new file, or null if not line-specific")
    description: str = Field(description="What the issue is, in 1-2 sentences")
    suggestion: str = Field(description="Concrete fix, in 1-2 sentences")


class CodeReview(dspy.Signature):
    """Review a single-file diff the way a senior CellProfiler maintainer would.

    Focus on: dead/unused code, project conventions (import order, TODO format,
    logging over print, library opts usage), and broken abstractions
    (raw values where enums exist, magic constants).

    Only flag real, concrete issues - skip vague suggestions or praise.
    Emit zero issues if the diff is clean.
    """
    file_path: str = dspy.InputField(desc="Path of the file being reviewed")
    diff: str = dspy.InputField(desc="Unified diff for this single file")
    issues: list[Issue] = dspy.OutputField(desc="Concrete review issues; empty list if none")


# -------- Data loading --------

def categorize_comment(body: str) -> str:
    b = body.lower()
    if any(k in b for k in ["not used", "no longer used", "unused", "not accessed"]):
        return "unused-code"
    if any(k in b for k in ["import", "todo:", "print", "logging", "naming"]):
        return "convention"
    if any(k in b for k in ["enum", "constant", "library opts", "abstraction", "magic"]):
        return "abstraction"
    return "style"


def gold_to_issues(gold_comments: list[dict]) -> list[Issue]:
    """Convert gnodar01's raw comments into structured Issue objects for use as demos."""
    return [
        Issue(
            category=categorize_comment(c["body"]),
            line=c["line"],
            description=c["body"],
            suggestion="",
        )
        for c in gold_comments
    ]


def load_examples(path: Path) -> list[dspy.Example]:
    raw = json.loads(path.read_text())
    out = []
    for r in raw:
        ex = dspy.Example(
            file_path=r["file"],
            diff=r["diff"],
            gold_comments=[c["body"] for c in r["gold_comments"]],
            issues=gold_to_issues(r["gold_comments"]),
        ).with_inputs("file_path", "diff")
        out.append(ex)
    return out


# -------- Metric: LLM-as-judge recall + light precision --------

class CommentMatch(dspy.Signature):
    """Decide whether a predicted review issue substantively matches a gold reviewer comment.

    Match = same concern about the same code location. Different wording is fine.
    Off-by-one on line numbers is fine. Different category labels are fine.
    """
    gold_comment: str = dspy.InputField(desc="The actual reviewer's comment")
    predicted_issue: str = dspy.InputField(desc="The program's predicted issue")
    file_diff: str = dspy.InputField(desc="The diff being reviewed (for context)")
    matches: bool = dspy.OutputField()


_JUDGE_LM_CACHED = None

def get_judge_lm():
    global _JUDGE_LM_CACHED
    if _JUDGE_LM_CACHED is None:
        kw = {"max_tokens": 2000}
        if "opus" not in JUDGE_LM:
            kw["temperature"] = 0.0
        _JUDGE_LM_CACHED = dspy.LM(JUDGE_LM, **kw)
    return _JUDGE_LM_CACHED


def review_metric(example: dspy.Example, prediction, trace=None) -> float:
    """Recall against gold comments. Returns 0..1.

    For each gold comment, check whether any predicted issue matches it.
    Examples with no gold get full credit (neutral).
    """
    gold = example.gold_comments
    pred_issues = prediction.issues or []

    if not gold:
        return 1.0

    judge = dspy.ChainOfThought(CommentMatch)
    matched = 0
    with dspy.context(lm=get_judge_lm()):
        for g in gold:
            for p in pred_issues:
                p_str = f"[{p.category}] line {p.line}: {p.description} | suggestion: {p.suggestion}"
                try:
                    r = judge(gold_comment=g, predicted_issue=p_str, file_diff=example.diff[:4000])
                    if r.matches:
                        matched += 1
                        break
                except Exception as e:
                    print(f"  judge error: {e}")
                    continue
    return matched / len(gold)


# -------- Eval --------

def evaluate(program, examples: list[dspy.Example], label: str) -> float:
    print(f"\n=== Eval: {label} ({len(examples)} examples) ===")
    total = 0.0
    n_scored = 0
    for i, ex in enumerate(examples):
        try:
            pred = program(file_path=ex.file_path, diff=ex.diff)
        except Exception as e:
            print(f"  [{i}] {ex.file_path}: predict failed: {e}")
            continue
        score = review_metric(ex, pred)
        n_pred = len(pred.issues or [])
        n_gold = len(ex.gold_comments)
        marker = " " if not ex.gold_comments else "*"
        print(f"  {marker}[{i}] {ex.file_path[-50:]:50s} gold={n_gold:2d} pred={n_pred:2d} score={score:.2f}")
        total += score
        n_scored += 1
    avg = total / max(n_scored, 1)
    print(f"  -> mean recall (incl. negatives at 1.0): {avg:.3f}")
    # Score restricted to examples with gold (the meaningful signal):
    gold_only = [(ex, sc) for ex, sc in zip(examples, [None]*len(examples))]  # placeholder
    return avg


def evaluate_positive_only(program, examples: list[dspy.Example], label: str):
    """Stricter eval: only count examples with gold comments."""
    pos = [e for e in examples if e.gold_comments]
    print(f"\n=== Eval (gold-only): {label} ({len(pos)} examples) ===")
    total = 0.0
    for i, ex in enumerate(pos):
        try:
            pred = program(file_path=ex.file_path, diff=ex.diff)
        except Exception as e:
            print(f"  [{i}] error: {e}")
            continue
        score = review_metric(ex, pred)
        n_pred = len(pred.issues or [])
        n_gold = len(ex.gold_comments)
        print(f"  [{i}] {ex.file_path[-50:]:50s} gold={n_gold:2d} pred={n_pred:2d} recall={score:.2f}")
        total += score
    avg = total / max(len(pos), 1)
    print(f"  -> mean recall on gold examples: {avg:.3f}")
    return avg


# -------- Commands --------

def setup_lm():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)
    # Opus 4.7 doesn't accept `temperature`. Set it only for non-opus models.
    kwargs = {"max_tokens": 4000}
    if "opus" not in PROGRAM_LM:
        kwargs["temperature"] = 0.0
    dspy.configure(lm=dspy.LM(PROGRAM_LM, **kwargs))


def cmd_baseline():
    setup_lm()
    test = load_examples(DATA / "test.json")
    program = dspy.Predict(CodeReview)
    evaluate_positive_only(program, test, "baseline (zero-shot)")


def cmd_compile():
    setup_lm()
    train = load_examples(DATA / "train.json")
    test = load_examples(DATA / "test.json")
    program = dspy.Predict(CodeReview)

    print(f"Train: {len(train)} examples ({sum(1 for e in train if e.gold_comments)} with gold)")

    # Restrict optimizer training to examples with gold comments - clearer signal.
    train_pos = [e for e in train if e.gold_comments]

    print("\nBaseline first:")
    evaluate_positive_only(program, test, "baseline")

    print("\nCompiling with LabeledFewShot (uses gnodar01's actual comments as demos)...")
    optimizer = dspy.LabeledFewShot(k=5)
    compiled = optimizer.compile(program, trainset=train_pos)

    compiled.save(str(ARTIFACT))
    print(f"Saved compiled program to {ARTIFACT}")

    print("\nCompiled eval:")
    evaluate_positive_only(compiled, test, "compiled")


def cmd_compare():
    setup_lm()
    test = load_examples(DATA / "test.json")
    baseline = dspy.Predict(CodeReview)

    if not ARTIFACT.exists():
        print(f"No compiled artifact at {ARTIFACT}; run `compile` first.")
        sys.exit(1)

    compiled = dspy.Predict(CodeReview)
    compiled.load(str(ARTIFACT))

    pos = [e for e in test if e.gold_comments]
    print(f"\nComparing on {len(pos)} held-out files with gold comments:\n")

    for ex in pos:
        print(f"--- {ex.file_path} ---")
        print(f"\nGOLD ({len(ex.gold_comments)}):")
        for c in ex.gold_comments:
            print(f"  - {c[:120]}")

        for label, prog in [("BASELINE", baseline), ("COMPILED", compiled)]:
            print(f"\n{label}:")
            try:
                pred = prog(file_path=ex.file_path, diff=ex.diff)
                for issue in pred.issues:
                    print(f"  - [{issue.category}] line {issue.line}: {issue.description}")
            except Exception as e:
                print(f"  error: {e}")
        print()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    {"baseline": cmd_baseline, "compile": cmd_compile, "compare": cmd_compare}[cmd]()
