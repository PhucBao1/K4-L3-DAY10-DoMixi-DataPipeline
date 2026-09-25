from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from core.utils import now_utc, write_json
from ingestion.cleaning import _build_text_for_embedding

SEED = 42
DROP_LATEST_RATIO = 0.20
BLANK_SUMMARY_ROWS = 3
NOISE_ROWS = 3
TRUNCATE_TITLE_ROWS = 3
TRUNCATED_TITLE_CHARS = 7
STALE_DATE_ROWS = 5
STALE_SHIFT_DAYS = 365
DUPLICATE_ROWS = 4
NOISE_TOKENS = ["#@!%", "~~~", "¿¿", "lorem-ipsum", "��", "<br/>", "&&&", "0xDEADBEEF"]


def _log_entry(name: str, description: str, df: pd.DataFrame, positions: list[int], **extra: Any) -> dict[str, Any]:
    return {
        "corruption": name,
        "description": description,
        "affected_rows": len(positions),
        "affected_paper_ids": [str(df.iloc[pos]["paper_id"]) for pos in positions],
        **extra,
    }


def _noise(rng: np.random.Generator) -> str:
    return " ".join(rng.choice(NOISE_TOKENS, size=4, replace=True).tolist())


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path) -> pd.DataFrame:
    """Simulate 6 dang data corruption thuong gap tren cleaned dataframe va ghi log.

    1. drop_latest_records  2. blank_summary  3. inject_noise
    4. truncate_title       5. stale_date     6. duplicate_rows

    Cac kich ban 2-5 tac dong len nhom dong rieng biet (seed co dinh -> tai lap duoc),
    sau do cac cot phai sinh (`summary_chars`, `text_for_embedding`) duoc tinh lai de
    vector store phan anh dung du lieu bi hong.
    """
    rng = np.random.default_rng(SEED)
    rows_before = len(df)
    corrupted = df.sort_values(["published", "paper_id"], ascending=[False, True]).reset_index(drop=True).copy()
    log: list[dict[str, Any]] = []

    # 1. Drop latest records: mat 20% ban ghi moi nhat (ingestion bo sot du lieu tuoi).
    drop_count = math.ceil(len(corrupted) * DROP_LATEST_RATIO)
    log.append(
        _log_entry(
            "drop_latest_records",
            f"Dropped the {DROP_LATEST_RATIO:.0%} most recent papers (simulates a failed incremental ingestion).",
            corrupted,
            list(range(drop_count)),
        )
    )
    corrupted = corrupted.iloc[drop_count:].reset_index(drop=True)

    # Chia cac nhom dong rieng biet cho kich ban 2-5.
    permutation = rng.permutation(len(corrupted)).tolist()
    sizes = [BLANK_SUMMARY_ROWS, NOISE_ROWS, TRUNCATE_TITLE_ROWS, STALE_DATE_ROWS]
    groups, start = [], 0
    for size in sizes:
        groups.append(sorted(permutation[start : start + size]))
        start += size
    blank_rows, noise_rows, truncate_rows, stale_rows = groups

    # 2. Blank summary: scraper tra ve abstract rong.
    log.append(
        _log_entry("blank_summary", "Replaced the abstract with an empty string.", corrupted, blank_rows)
    )
    corrupted.loc[blank_rows, "summary"] = ""

    # 3. Inject noise: chen ky tu rac vao dau abstract (loi encoding / HTML sot lai).
    log.append(
        _log_entry("inject_noise", "Prepended garbage tokens to the abstract.", corrupted, noise_rows)
    )
    for pos in noise_rows:
        corrupted.at[pos, "summary"] = f"{_noise(rng)} {corrupted.at[pos, 'summary']} {_noise(rng)}"

    # 4. Truncate title: title bi cat con < 8 ky tu.
    log.append(
        _log_entry(
            "truncate_title",
            f"Truncated the title to {TRUNCATED_TITLE_CHARS} characters.",
            corrupted,
            truncate_rows,
            original_titles=[str(corrupted.at[pos, "title"]) for pos in truncate_rows],
        )
    )
    corrupted.loc[truncate_rows, "title"] = corrupted.loc[truncate_rows, "title"].str[:TRUNCATED_TITLE_CHARS]

    # 5. Stale date: lui ngay xuat ban 365 ngay (du lieu bi moc).
    log.append(
        _log_entry(
            "stale_date",
            f"Shifted the published date back by {STALE_SHIFT_DAYS} days.",
            corrupted,
            stale_rows,
            original_published=[str(corrupted.at[pos, "published"]) for pos in stale_rows],
        )
    )
    shifted = pd.to_datetime(corrupted.loc[stale_rows, "published"]) - pd.Timedelta(days=STALE_SHIFT_DAYS)
    corrupted.loc[stale_rows, "published"] = shifted.dt.strftime("%Y-%m-%d")
    corrupted.loc[stale_rows, "age_days"] = corrupted.loc[stale_rows, "age_days"].astype(int) + STALE_SHIFT_DAYS

    # Tinh lai cot phai sinh de index phan anh du lieu hong.
    corrupted["summary_chars"] = corrupted["summary"].str.len().astype(int)
    corrupted["text_for_embedding"] = corrupted.apply(_build_text_for_embedding, axis=1)

    # 6. Duplicate rows: nhan ban dong (job ingest chay 2 lan, khong upsert).
    duplicate_rows = sorted(rng.choice(len(corrupted), size=DUPLICATE_ROWS, replace=False).tolist())
    log.append(
        _log_entry(
            "duplicate_rows",
            "Appended exact copies of existing rows (non-idempotent re-ingestion).",
            corrupted,
            duplicate_rows,
        )
    )
    corrupted = pd.concat([corrupted, corrupted.iloc[duplicate_rows]], ignore_index=True)

    write_json(
        output_log_path,
        {
            "generated_at": now_utc().isoformat(),
            "seed": SEED,
            "rows_before": rows_before,
            "rows_after": len(corrupted),
            "corruption_types": len(log),
            "corruptions": log,
        },
    )
    return corrupted
