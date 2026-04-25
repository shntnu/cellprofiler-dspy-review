"""Peek at what the baseline produces vs gold on the test set."""
import json, os, sys
import dspy
from review import CodeReview, load_examples, DATA, PROGRAM_LM

_kw = {"max_tokens": 4000}
if "opus" not in PROGRAM_LM:
    _kw["temperature"] = 0.0
dspy.configure(lm=dspy.LM(PROGRAM_LM, **_kw))
test = load_examples(DATA / "test.json")
program = dspy.Predict(CodeReview)

for ex in test:
    if not ex.gold_comments:
        continue
    print(f"\n========== {ex.file_path} ==========")
    print(f"\nGOLD ({len(ex.gold_comments)}):")
    for c in ex.gold_comments:
        print(f"  - {c[:140]}")
    pred = program(file_path=ex.file_path, diff=ex.diff)
    print(f"\nPREDICTED ({len(pred.issues)}):")
    for i in pred.issues:
        print(f"  - [{i.category}] line {i.line}: {i.description[:120]}")
