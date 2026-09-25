from __future__ import annotations

from dataclasses import asdict, dataclass
import html
from pathlib import Path
import re
import time

import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

CROSSREF_WORKS_URL = "https://api.crossref.org/works"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4
REQUEST_TIMEOUT_SECONDS = 30
USER_AGENT = "day10-data-observability-lab/0.1 (student lab)"


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _strip_markup(value: str) -> str:
    """Bo tag JATS/HTML (vd `<jats:p>`) va chuan hoa khoang trang."""
    without_tags = re.sub(r"<[^>]+>", " ", value or "")
    return normalize_whitespace(html.unescape(without_tags))


def _first_text(value) -> str:
    """Crossref tra `title` dang list; lay phan tu dau tien khong rong."""
    if isinstance(value, list):
        for item in value:
            text = _strip_markup(str(item))
            if text:
                return text
        return ""
    return _strip_markup(str(value or ""))


def _date_from_parts(field: dict | None) -> str:
    """Chuyen `{"date-parts": [[2026, 5, 20]]}` thanh `2026-05-20` (thieu thang/ngay -> 01)."""
    if not field:
        return ""
    parts = (field.get("date-parts") or [[]])[0]
    if not parts or parts[0] is None:
        return ""
    year, month, day = (list(parts) + [1, 1])[:3]
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _published_date(item: dict) -> str:
    for key in ("published", "published-online", "published-print", "issued"):
        value = _date_from_parts(item.get(key))
        if value:
            return value
    return ""


def _updated_date(item: dict, published: str) -> str:
    for key in ("created", "deposited", "indexed"):
        date_time = (item.get(key) or {}).get("date-time", "")
        if date_time:
            return date_time[:10]
    return published


def _author_names(item: dict) -> list[str]:
    names: list[str] = []
    for author in item.get("author") or []:
        name = normalize_whitespace(
            " ".join(part for part in (author.get("given", ""), author.get("family", "")) if part)
        )
        name = name or normalize_whitespace(author.get("name", ""))
        if name:
            names.append(name)
    return names


def _pdf_url(item: dict, fallback: str) -> str:
    for link in item.get("link") or []:
        if "pdf" in (link.get("content-type") or "").lower() and link.get("URL"):
            return link["URL"]
    return fallback


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord.

    Bo qua record thieu DOI/title/abstract/ngay xuat ban va record trung DOI.
    """
    records: list[PaperRecord] = []
    seen_ids: set[str] = set()
    for item in (payload.get("message") or {}).get("items") or []:
        paper_id = normalize_whitespace(item.get("DOI", "")).lower()
        title = _first_text(item.get("title"))
        summary = _strip_markup(item.get("abstract", ""))
        published = _published_date(item)
        if not paper_id or not title or not summary or not published or paper_id in seen_ids:
            continue
        seen_ids.add(paper_id)

        categories = [normalize_whitespace(subject) for subject in item.get("subject") or [] if subject]
        abs_url = item.get("URL") or f"https://doi.org/{paper_id}"
        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=_author_names(item),
                categories=categories,
                primary_category=categories[0] if categories else "",
                published=published,
                updated=_updated_date(item, published),
                abs_url=abs_url,
                pdf_url=_pdf_url(item, abs_url),
                comment=f"Crossref record {paper_id}",
            )
        )
    return records


def _request_crossref(settings: Settings) -> dict:
    params = {
        "query": settings.source_query,
        "filter": settings.source_filter,
        "rows": settings.max_results,
        "sort": "published",
        "order": "desc",
    }
    headers = {"User-Agent": USER_AGENT}
    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = requests.get(
                CROSSREF_WORKS_URL, params=params, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS
            )
            if response.status_code in RETRYABLE_STATUS:
                raise requests.HTTPError(f"Crossref returned {response.status_code}", response=response)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and status not in RETRYABLE_STATUS:
                break
            if attempt < MAX_ATTEMPTS:
                retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt
                print(f"[crossref] Attempt {attempt} failed ({exc}); retrying in {delay:.0f}s")
                time.sleep(delay)
    raise RuntimeError(f"Crossref API unavailable after {MAX_ATTEMPTS} attempts: {last_error}")


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Lay payload (live API hoac snapshot), luu raw response, parse va luu records.

    - Mac dinh (Dev/Offline): doc snapshot `settings.paths.raw_api_response` neu da ton tai.
    - `REFRESH_SOURCE=1` hoac chua co snapshot: goi Crossref API voi retry 429/5xx;
      neu API loi va snapshot con ton tai thi fallback ve snapshot (khong ghi de raw goc).
    """
    snapshot_path = settings.paths.raw_api_response
    payload: dict | None = None

    if settings.refresh_source or not snapshot_path.exists():
        try:
            payload = _request_crossref(settings)
            if not parse_crossref_payload(payload):
                raise RuntimeError("Crossref API returned no usable records")
            write_json(snapshot_path, payload)
            print(f"[crossref] Live API: saved raw response to {snapshot_path}")
        except RuntimeError as exc:
            if not snapshot_path.exists():
                raise
            print(f"[crossref] {exc}. Falling back to local snapshot {snapshot_path}")
            payload = None

    if payload is None:
        payload = read_json(snapshot_path)
        print(f"[crossref] Offline mode: loaded snapshot {snapshot_path}")

    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(record) for record in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot records va map thanh `PaperRecord`."""
    return [PaperRecord(**row) for row in read_json(path)]
