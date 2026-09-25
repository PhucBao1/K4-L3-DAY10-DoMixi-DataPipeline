from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import html
import re

import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord

CLEAN_COLUMNS = [
    "paper_id",
    "title",
    "summary",
    "authors",
    "categories",
    "primary_category",
    "published",
    "updated",
    "abs_url",
    "pdf_url",
    "comment",
    "authors_joined",
    "categories_joined",
    "summary_chars",
    "age_days",
    "text_for_embedding",
]


def _clean_text(value: object) -> str:
    """Bo tag JATS/HTML con sot (vd `<jats:p>`), decode HTML entity va chuan hoa khoang trang."""
    text = re.sub(r"<[^>]+>", " ", "" if value is None else str(value))
    return normalize_whitespace(html.unescape(text))


def _normalize_list(values: list[str] | None) -> list[str]:
    """Chuan hoa khoang trang, bo phan tu rong va trung lap (giu thu tu)."""
    seen: set[str] = set()
    items: list[str] = []
    for value in values or []:
        text = _clean_text(value)
        if text and text.lower() not in seen:
            seen.add(text.lower())
            items.append(text)
    return items


def _build_text_for_embedding(row: pd.Series) -> str:
    return "\n".join(
        [
            f"Title: {row['title']}",
            f"Authors: {row['authors_joined']}",
            f"Published: {row['published']}",
            f"Categories: {row['categories_joined']}",
            f"Summary: {row['summary']}",
        ]
    )


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed.

    Buoc xu ly: chuan hoa text -> parse ngay -> tinh `age_days` -> tao cot helper
    (`authors_joined`, `categories_joined`, `summary_chars`, `text_for_embedding`)
    -> loc row xau -> khu trung lap theo `paper_id` -> sort.
    """
    if run_date.tzinfo is None:
        run_date = run_date.replace(tzinfo=UTC)
    run_day = pd.Timestamp(run_date.astimezone(UTC).date())

    df = pd.DataFrame([asdict(record) for record in records])
    if df.empty:
        return pd.DataFrame(columns=CLEAN_COLUMNS)

    for column in ("paper_id", "title", "summary", "primary_category", "abs_url", "pdf_url", "comment"):
        df[column] = df[column].map(_clean_text)
    df["paper_id"] = df["paper_id"].str.lower()
    df["authors"] = df["authors"].map(_normalize_list)
    df["categories"] = df["categories"].map(_normalize_list)
    df["primary_category"] = [
        primary or (categories[0] if categories else "")
        for primary, categories in zip(df["primary_category"], df["categories"])
    ]

    published = pd.to_datetime(df["published"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    updated = pd.to_datetime(df["updated"], errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()
    updated = updated.fillna(published)

    # Loc row xau: thieu khoa, thieu noi dung, hoac ngay xuat ban khong parse duoc.
    valid = (df["paper_id"] != "") & (df["title"] != "") & (df["summary"] != "") & published.notna()
    df, published, updated = df[valid].copy(), published[valid], updated[valid]

    df["published"] = published.dt.strftime("%Y-%m-%d")
    df["updated"] = updated.dt.strftime("%Y-%m-%d")
    df["age_days"] = (run_day - published).dt.days.astype(int)
    df["authors_joined"] = df["authors"].map(compact_join)
    df["categories_joined"] = df["categories"].map(compact_join)
    df["summary_chars"] = df["summary"].str.len().astype(int)
    df["text_for_embedding"] = df.apply(_build_text_for_embedding, axis=1)

    # Khu trung lap theo paper_id: giu ban cap nhat moi nhat.
    df = (
        df.sort_values(["paper_id", "updated"], ascending=[True, False])
        .drop_duplicates(subset="paper_id", keep="first")
        .sort_values(["published", "paper_id"], ascending=[False, True])
        .reset_index(drop=True)
    )
    return df[CLEAN_COLUMNS]
