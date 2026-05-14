from unittest.mock import MagicMock, call

from app.sheets import COLUMNS, _to_row, _upsert

MOTT_URL = "https://www.yelp.com/biz/mott-32-las-vegas-2"
MANGO_URL = "https://www.yelp.com/biz/mango-mango-dessert-las-vegas"

MOTT = {
    "name": "Mott 32",
    "biz_url": MOTT_URL,
    "category": "Chinese, Cocktail Bars",
    "rating": 4.0,
    "review_count": 1575,
    "price": "$$$$",
    "neighborhood": "Las Vegas, NV",
}

MANGO = {
    "name": "Mango Mango Dessert",
    "biz_url": MANGO_URL,
    "category": "Desserts, Bubble Tea",
    "rating": 4.5,
    "review_count": 803,
    "price": None,
    "neighborhood": "Las Vegas, NV",
}


def _ws(rows=None):
    ws = MagicMock()
    ws.get_all_values.return_value = rows if rows is not None else []
    return ws


# ── _to_row ───────────────────────────────────────────────────────────────────

def test_to_row_name_is_plain_text():
    row = _to_row(MOTT)
    assert row[0] == "Mott 32"


def test_to_row_biz_url_is_hyperlink():
    row = _to_row(MOTT)
    assert row[1] == f'=HYPERLINK("{MOTT_URL}","{MOTT_URL}")'


def test_to_row_fields_in_order():
    row = _to_row(MOTT)
    assert row[2] == "Chinese, Cocktail Bars"
    assert row[3] == 4.0
    assert row[4] == 1575
    assert row[5] == "$$$$"
    assert row[6] == "Las Vegas, NV"


def test_to_row_none_price_becomes_empty_string():
    row = _to_row(MANGO)
    assert row[5] == ""


def test_to_row_name_with_quotes_stays_as_is():
    biz = {**MOTT, "name": 'Cafe "Joe"'}
    row = _to_row(biz)
    assert row[0] == 'Cafe "Joe"'


def test_to_row_empty_url_produces_empty_biz_url():
    row = _to_row({**MOTT, "biz_url": None})
    assert row[0] == "Mott 32"
    assert row[1] == ""


# ── _upsert: empty sheet ──────────────────────────────────────────────────────

def test_empty_sheet_writes_header():
    ws = _ws([])
    _upsert(ws, [MOTT])
    ws.insert_row.assert_called_once_with(COLUMNS, 1)


def test_empty_sheet_formats_header_bold():
    ws = _ws([])
    _upsert(ws, [MOTT])
    ws.format.assert_called_once()
    assert "bold" in str(ws.format.call_args)


def test_empty_sheet_all_businesses_are_new():
    ws = _ws([])
    result = _upsert(ws, [MOTT, MANGO])
    assert result == {"new": 2, "updated": 0}
    ws.append_rows.assert_called_once()
    ws.batch_update.assert_not_called()


# ── _upsert: sheet has data but no header ────────────────────────────────────

def test_inserts_header_when_sheet_has_data_but_no_header():
    # Simulate sheet with 30 rows of raw data and no header
    raw_rows = [["Mott 32", MOTT_URL, "Chinese", 4.0, 1575, "$$$$", "Las Vegas, NV"]]
    ws = _ws(raw_rows)
    _upsert(ws, [])
    ws.insert_row.assert_called_once_with(COLUMNS, 1)


def test_header_inserted_before_existing_data_shifts_row_numbers():
    # If there are 2 data rows and we insert a header at row 1,
    # the first data row should now be at row 2 for update targeting.
    raw_rows = [
        ["Mott 32", MOTT_URL, "Chinese", 4.0, 1575, "$$$$", "Las Vegas, NV"],
        ["Mango Mango Dessert", MANGO_URL, "Desserts", 4.5, 803, "", "Las Vegas, NV"],
    ]
    ws = _ws(raw_rows)
    result = _upsert(ws, [MOTT])
    assert result == {"new": 0, "updated": 1}
    updates = ws.batch_update.call_args[0][0]
    assert updates[0]["range"] == "A2"


# ── _upsert: existing rows with header ───────────────────────────────────────

def _existing(*businesses):
    # Simulates get_all_values(): header row + rows with raw biz_url (formatted value)
    rows = [COLUMNS]
    for biz in businesses:
        def _v(key, b=biz):
            v = b.get(key)
            return "" if v is None else v
        rows.append([
            _v("name"), _v("biz_url"), _v("category"),
            _v("rating"), _v("review_count"), _v("price"), _v("neighborhood"),
        ])
    return rows


def test_all_existing_counts_as_updated():
    ws = _ws(_existing(MOTT, MANGO))
    result = _upsert(ws, [MOTT, MANGO])
    assert result == {"new": 0, "updated": 2}
    ws.batch_update.assert_called_once()
    ws.append_rows.assert_not_called()


def test_update_targets_correct_row_number():
    """Row 1 = header, row 2 = first biz → update range should be A2."""
    ws = _ws(_existing(MOTT))
    _upsert(ws, [MOTT])
    updates = ws.batch_update.call_args[0][0]
    assert updates[0]["range"] == "A2"


def test_mixed_new_and_updated():
    ws = _ws(_existing(MOTT))
    result = _upsert(ws, [MOTT, MANGO])
    assert result == {"new": 1, "updated": 1}


def test_no_header_written_when_header_already_exists():
    ws = _ws(_existing(MOTT))
    _upsert(ws, [MOTT])
    ws.insert_row.assert_not_called()
