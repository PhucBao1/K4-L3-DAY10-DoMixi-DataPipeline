from __future__ import annotations

from typing import Any

import pandas as pd

from core.utils import first_sentence, write_json

# 10 cau hoi phu du 4 nhom nghiep vu. Cau hoi dung tu khoa ma `retrieval.qa._extract_answer`
# nhan dien ("who authored", "when was", "what categories") va dat title trong dau nhay don
# de QA co the exact-lookup.
QUESTION_PLAN = ["summary", "authors", "date", "categories"] * 2 + ["summary", "authors"]
MIN_DOCUMENTS = len(QUESTION_PLAN)

QUESTION_TEMPLATES = {
    "summary": "What is the summary of the paper '{title}'?",
    "authors": "Who authored the paper '{title}'?",
    "date": "When was the paper '{title}' published?",
    "categories": "What categories does the paper '{title}' belong to?",
}


def _ground_truth(row: pd.Series, question_type: str) -> str:
    if question_type == "summary":
        return first_sentence(row["summary"])
    if question_type == "authors":
        return row["authors_joined"]
    if question_type == "date":
        return str(row["published"])
    return row["categories_joined"]


def _select_papers(df: pd.DataFrame, count: int) -> pd.DataFrame:
    """Chon `count` paper trai deu tu moi nhat den cu nhat (deterministic).

    Bao gom ca cac paper moi nhat de kich ban "drop latest records" anh huong den test set.
    """
    ordered = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)
    step = (len(ordered) - 1) / (count - 1) if count > 1 else 0
    positions = sorted({round(i * step) for i in range(count)})
    return ordered.iloc[positions].reset_index(drop=True)


def build_test_set(df: pd.DataFrame, output_path) -> list[dict[str, Any]]:
    """Tao bo evaluation set (10 cau, 4 nhom) tu cleaned dataframe va ghi JSON."""
    candidates = df.drop_duplicates(subset="paper_id")
    candidates = candidates[
        (candidates["title"].str.len() > 0)
        & (candidates["summary"].str.len() > 0)
        & (candidates["authors_joined"].str.len() > 0)
        & (candidates["categories_joined"].str.len() > 0)
    ]
    if len(candidates) < MIN_DOCUMENTS:
        raise ValueError(f"Need at least {MIN_DOCUMENTS} valid documents to build the test set, got {len(candidates)}.")

    papers = _select_papers(candidates, len(QUESTION_PLAN))
    test_set: list[dict[str, Any]] = []
    for number, (question_type, (_, row)) in enumerate(zip(QUESTION_PLAN, papers.iterrows()), start=1):
        test_set.append(
            {
                "id": f"eval_{number:03d}",
                "question_type": question_type,
                "question": QUESTION_TEMPLATES[question_type].format(title=row["title"]),
                "ground_truth": _ground_truth(row, question_type),
                "ground_truth_doc_ids": [row["paper_id"]],
            }
        )

    write_json(output_path, test_set)
    return test_set
