"""Verify the pandas code path in symbol_master against a real Fyers-shaped CSV.

The Fyers symbol master is headerless, 21 columns, may carry a UTF-8 BOM and
contains blank cells.  ``parse_csv`` must not shift column names, must keep
blanks as None, and must drop rows without a numeric ``fytoken``.  These tests
exercise the real parser (pandas is a hard dependency of this module) rather
than a stub.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.symbol_master import (  # noqa: E402
    FYERS_COLUMNS,
    SymbolMasterDownloader,
)


def _row(**overrides):
    """Build one headerless 21-field record with parser-valid defaults."""
    row = {name: "" for name in FYERS_COLUMNS}
    row.update(
        {
            "fytoken": "10001",
            "symbol_description": "NIFTY",
            "symbol_ticker": "NSE:NIFTY50-INDEX",
            "exchange_code": "NSE_CM",
            "segment": "NSE_CM",
            # 10 = index in the cash-market master.
            "instrument_type": "10",
            "lot_size": "1",
            "tick_size": "0.05",
        }
    )
    row.update(overrides)
    return ",".join(str(row[name]) for name in FYERS_COLUMNS)


def test_parse_csv_reads_real_shape():
    csv = "\n".join(
        [
            _row(fytoken="10001", symbol_description="NIFTY",
                 symbol_ticker="NSE:NIFTY50-INDEX", instrument_type="10"),
            _row(fytoken="10002", symbol_description="SBIN",
                 symbol_ticker="NSE:SBIN-EQ", instrument_type="0"),
        ]
    )

    rows = SymbolMasterDownloader().parse_csv(csv, "NSE_CM")

    assert len(rows) == 2
    assert rows[0]["symbol"] == "NSE:NIFTY50-INDEX"
    assert rows[1]["symbol"] == "NSE:SBIN-EQ"
    assert rows[0]["fyers_token"] == "10001"


def test_parse_csv_handles_bom_and_blank_cells():
    csv = "\ufeff" + _row(strike_price="", option_type="") + "\n"

    rows = SymbolMasterDownloader().parse_csv(csv, "NSE_CM")

    assert len(rows) == 1
    # Blank cells stay empty rather than becoming NaN.
    assert rows[0]["strike"] is None
    assert rows[0]["expiry"] is None


def test_parse_csv_promotes_option_contracts():
    """A CE/PE row with a blank instrument_type must still be stored as an option."""
    csv = _row(
        symbol_description="NIFTY",
        symbol_ticker="NSE:NIFTY25JAN24500CE",
        instrument_type="",
        option_type="CE",
        strike_price="24500",
    )

    rows = SymbolMasterDownloader().parse_csv(csv, "NSE_FO")

    assert len(rows) == 1
    assert rows[0]["instrument_type"] == "12"
    assert rows[0]["option_type"] == "CE"
    assert rows[0]["strike"] == 24500.0


def test_parse_csv_drops_rows_without_numeric_fytoken():
    csv = "\n".join([_row(fytoken="", symbol_ticker="NSE:GHOST-EQ"), _row()])

    rows = SymbolMasterDownloader().parse_csv(csv, "NSE_CM")

    assert [r["symbol"] for r in rows] == ["NSE:NIFTY50-INDEX"]


def test_parse_csv_filters_wrong_segment_instrument_types():
    """NSE_CM keeps only cash-market codes, so an F&O row must be dropped."""
    csv = _row(fytoken="10001", symbol="NSE:NIFTY50-INDEX", instrument_type="12")

    assert SymbolMasterDownloader().parse_csv(csv, "NSE_CM") == []


def test_blank_cells_do_not_drop_the_row():
    """Regression: NaN cells are truthy, so strptime/isdigit raised and the
    whole row was discarded with only a warning.  Equities have no expiry."""
    csv = _row(
        fytoken="10002",
        symbol_description="SBIN",
        symbol_ticker="NSE:SBIN-EQ",
        instrument_type="0",
        expiry_date="",
        strike_price="",
        lot_size="",
        option_type="",
    )

    rows = SymbolMasterDownloader().parse_csv(csv, "NSE_CM")

    assert len(rows) == 1
    assert rows[0]["symbol"] == "NSE:SBIN-EQ"
    assert rows[0]["expiry"] is None
    assert rows[0]["strike"] is None
    assert rows[0]["lot_size"] is None


def test_parse_csv_empty_input_returns_empty_list():
    assert SymbolMasterDownloader().parse_csv("   ", "NSE_CM") == []


def test_pandas_is_importable_and_modern():
    """pandas is a hard dependency; record the version the suite ran against."""
    import pandas

    assert pandas.__version__


def test_validate_csv_structure_passes_for_valid_csv():
    """_validate_csv_structure returns True for valid Fyers CSV."""
    csv = "\n".join([
        _row(fytoken="10001", symbol_ticker="NSE:NIFTY50-INDEX", instrument_type="10"),
        _row(fytoken="10002", symbol_ticker="NSE:SBIN-EQ", instrument_type="0"),
    ])
    downloader = SymbolMasterDownloader()
    assert downloader._validate_csv_structure(csv, "NSE_CM") is True


def test_validate_csv_structure_fails_for_empty_csv():
    """_validate_csv_structure returns False for empty CSV."""
    downloader = SymbolMasterDownloader()
    assert downloader._validate_csv_structure("   ", "NSE_CM") is False
    assert downloader._validate_csv_structure("", "NSE_CM") is False


def test_validate_csv_structure_fails_for_missing_columns():
    """_validate_csv_structure returns False when required columns missing."""
    # CSV with only 5 columns instead of 21
    csv = "1,2,3,4,5\n6,7,8,9,10"
    downloader = SymbolMasterDownloader()
    assert downloader._validate_csv_structure(csv, "NSE_CM") is False


def test_validate_instrument_types_passes_for_cash_market():
    """_validate_instrument_types accepts valid NSE_CM instrument types."""
    instruments = [
        {"instrument_type": "0", "symbol_ticker": "NSE:SBIN-EQ"},
        {"instrument_type": "10", "symbol_ticker": "NSE:NIFTY50-INDEX"},
    ]
    downloader = SymbolMasterDownloader()
    assert downloader._validate_instrument_types(instruments, "NSE_CM") is True


def test_validate_instrument_types_fails_for_wrong_types():
    """_validate_instrument_types rejects unexpected instrument types."""
    instruments = [
        {"instrument_type": "12", "symbol_ticker": "NSE:NIFTY25JAN24500CE"},  # option type in CM
    ]
    downloader = SymbolMasterDownloader()
    assert downloader._validate_instrument_types(instruments, "NSE_CM") is False


def test_validate_instrument_types_passes_for_fo():
    """_validate_instrument_types accepts valid NSE_FO instrument types."""
    instruments = [
        {"instrument_type": "12", "symbol_ticker": "NSE:NIFTY25JAN24500CE", "option_type": "CE"},
        {"instrument_type": "11", "symbol_ticker": "NSE:NIFTY25JANFUT", "option_type": ""},
    ]
    downloader = SymbolMasterDownloader()
    assert downloader._validate_instrument_types(instruments, "NSE_FO") is True


def test_validate_option_contracts_passes_for_valid_options():
    """_validate_option_contracts returns True for contracts with CE/PE, expiry, strike."""
    instruments = [
        {"option_type": "CE", "expiry": "2025-01-23", "strike": 24500.0},
        {"option_type": "PE", "expiry": "2025-01-23", "strike": 24500.0},
    ]
    downloader = SymbolMasterDownloader()
    assert downloader._validate_option_contracts(instruments) is True


def test_validate_option_contracts_fails_when_no_options():
    """_validate_option_contracts returns False when no CE/PE contracts present."""
    instruments = [
        {"option_type": "", "expiry": "2025-01-23", "strike": 24500.0},  # future
        {"option_type": "XX", "expiry": "2025-01-23", "strike": 24500.0},  # invalid
    ]
    downloader = SymbolMasterDownloader()
    assert downloader._validate_option_contracts(instruments) is False


def test_validate_option_contracts_warns_for_missing_fields():
    """_validate_option_contracts still returns True but logs warning for incomplete data."""
    instruments = [
        {"option_type": "CE", "expiry": None, "strike": None},
        {"option_type": "PE", "expiry": "2025-01-23", "strike": 24500.0},
    ]
    downloader = SymbolMasterDownloader()
    # Should pass but log warning - we just check it returns True (doesn't fail hard)
    assert downloader._validate_option_contracts(instruments) is True
