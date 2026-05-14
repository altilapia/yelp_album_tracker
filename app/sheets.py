from __future__ import annotations

import gspread
from gspread import Worksheet

from app.config import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEET_ID, GOOGLE_WORKSHEET_NAME

COLUMNS = [
    "name",
    "biz_url",
    "category",
    "rating",
    "review_count",
    "price",
    "neighborhood",
]

_HEADER_RANGE = f"A1:{chr(ord('A') + len(COLUMNS) - 1)}1"


def _to_row(biz: dict) -> list:
    def _v(key):
        v = biz.get(key)
        return "" if v is None else v

    url = _v("biz_url")
    name = _v("name")
    url_link = f'=HYPERLINK("{url}","{url}")' if url else ""

    return [
        name,
        url_link,
        _v("category"),
        _v("rating"),
        _v("review_count"),
        _v("price"),
        _v("neighborhood"),
    ]


def _write_header(ws: Worksheet) -> None:
    ws.insert_row(COLUMNS, 1)
    ws.format(_HEADER_RANGE, {"textFormat": {"bold": True}})


def _upsert(ws: Worksheet, businesses: list[dict]) -> dict:
    """Updates existing rows (matched by biz_url) and appends new ones."""
    all_values = ws.get_all_values()

    if not all_values:
        _write_header(ws)
        all_values = [COLUMNS]
    elif not all_values[0] or all_values[0][0] != COLUMNS[0]:
        # Sheet has data but no header row — insert one now
        _write_header(ws)
        all_values = [COLUMNS] + all_values

    header = all_values[0]
    data_rows = all_values[1:]

    url_col = header.index("biz_url") if "biz_url" in header else 1

    # biz_url -> 1-based sheet row number
    url_to_row: dict[str, int] = {}
    for i, row in enumerate(data_rows, start=2):
        url = row[url_col] if len(row) > url_col else ""
        if url:
            url_to_row[url] = i

    updates: list[dict] = []
    new_rows: list[list] = []

    for biz in businesses:
        url = biz.get("biz_url", "")
        if url in url_to_row:
            updates.append({
                "range": f"A{url_to_row[url]}",
                "values": [_to_row(biz)],
            })
        else:
            new_rows.append(_to_row(biz))

    if updates:
        ws.batch_update(updates, value_input_option="USER_ENTERED")
    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return {"new": len(new_rows), "updated": len(updates)}


def _get_worksheet() -> Worksheet:
    client = gspread.service_account(filename=str(GOOGLE_CREDENTIALS_PATH))
    sh = client.open_by_key(GOOGLE_SHEET_ID)
    return sh.worksheet(GOOGLE_WORKSHEET_NAME)


def upload(businesses: list[dict]) -> dict:
    """Upsert businesses to the configured Google Sheet.

    Returns {'new': int, 'updated': int}.
    """
    return _upsert(_get_worksheet(), businesses)
