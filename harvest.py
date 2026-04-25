"""Harvest gnodar01 review comments + per-file diffs from CellProfiler PRs.

Output: data/examples.json - list of {pr, file, diff, gold_comments}
"""

import json
import subprocess
from pathlib import Path

REPO = "CellProfiler/CellProfiler"
REVIEWER = "gnodar01"

# PRs with substantive gnodar01 review comments (from earlier survey).
TRAIN_PRS = [5009, 5059, 5061, 5100, 5041, 4982, 5063, 5056, 5057, 5038,
             5103, 5034, 5064, 5096, 5010, 5011, 5018, 5097, 4994]
TEST_PRS = [5104]  # held out (11 gnodar01 comments)


def gh(path: str) -> object:
    out = subprocess.run(
        ["gh", "api", path, "--paginate"],
        capture_output=True, text=True, check=True,
    ).stdout
    # --paginate concatenates JSON arrays; if multiple pages, gh emits them as a single array.
    return json.loads(out)


def fetch_pr_files(pr: int) -> list[dict]:
    """Files changed in a PR with their patches."""
    return gh(f"repos/{REPO}/pulls/{pr}/files")


def fetch_pr_review_comments(pr: int) -> list[dict]:
    """Inline review comments on a PR."""
    return gh(f"repos/{REPO}/pulls/{pr}/comments")


def fetch_pr_meta(pr: int) -> dict:
    return gh(f"repos/{REPO}/pulls/{pr}")


def build_examples(prs: list[int]) -> list[dict]:
    examples = []
    for pr in prs:
        print(f"  PR #{pr}...")
        meta = fetch_pr_meta(pr)
        files = fetch_pr_files(pr)
        comments = [c for c in fetch_pr_review_comments(pr)
                    if c["user"]["login"] == REVIEWER]

        # Group gold comments by file path.
        by_path: dict[str, list[dict]] = {}
        for c in comments:
            by_path.setdefault(c["path"], []).append({
                "body": c["body"],
                "line": c.get("line"),
                "diff_hunk": c.get("diff_hunk", ""),
            })

        for f in files:
            patch = f.get("patch")
            if not patch:
                continue  # binary or too large
            # Skip very large patches to keep token budget sane.
            if len(patch) > 30000:
                continue
            examples.append({
                "pr": pr,
                "pr_title": meta["title"],
                "file": f["filename"],
                "diff": patch,
                "gold_comments": by_path.get(f["filename"], []),
            })
    return examples


def main():
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)

    print("Train PRs:")
    train = build_examples(TRAIN_PRS)
    (out_dir / "train.json").write_text(json.dumps(train, indent=2))

    print("Test PRs:")
    test = build_examples(TEST_PRS)
    (out_dir / "test.json").write_text(json.dumps(test, indent=2))

    n_train_with_gold = sum(1 for e in train if e["gold_comments"])
    n_test_with_gold = sum(1 for e in test if e["gold_comments"])
    print(f"\nTrain: {len(train)} files, {n_train_with_gold} with gold comments")
    print(f"Test:  {len(test)} files, {n_test_with_gold} with gold comments")
    print(f"Train gold comments total: {sum(len(e['gold_comments']) for e in train)}")
    print(f"Test gold comments total:  {sum(len(e['gold_comments']) for e in test)}")


if __name__ == "__main__":
    main()
