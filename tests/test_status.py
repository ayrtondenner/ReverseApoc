"""status.csv (D-20): the sparse per-function status table `gate` writes. Every name, address and
hash here is made up."""

from __future__ import annotations

import hashlib

import pytest

from reverseapoc.status import (
    MATCHED,
    PARTIAL,
    STATUS_COLUMNS,
    STATUS_COMMENT,
    StatusError,
    StatusRow,
    lf_sha256,
    read_status,
    status_path,
    write_status,
)

SHA = "ab" * 32
HEADER = ",".join(STATUS_COLUMNS)


def row(start: int, *, status: str = MATCHED, percent: float = 100.0, unit: str = "u_00010000",
        attempts: int = 0, sha: str = SHA, date: str = "2026-10-25") -> StatusRow:  # fmt: skip
    return StatusRow(start, f"func_{start:08X}", unit, status, percent, attempts, sha, date)


def test_columns_are_the_d20_schema():
    assert STATUS_COLUMNS == ("start", "name", "unit", "status", "best_percent", "attempts",
                              "source_sha256", "date")  # fmt: skip
    assert STATUS_COMMENT == "# written by: uv run reverseapoc gate EXE/UNIT; do not edit"


def test_status_round_trip(tmp_path):
    path = status_path(tmp_path / "config", "syn")
    assert path == tmp_path / "config" / "syn" / "status.csv"
    rows = [row(0x10020, status=PARTIAL, percent=73.5, attempts=3), row(0x10000, attempts=1)]
    write_status(path, rows)
    data = path.read_bytes()
    assert b"\r" not in data
    lines = data.decode("utf-8").split("\n")
    assert lines[0] == STATUS_COMMENT
    assert lines[1] == HEADER
    assert lines[2] == f"0x00010000,func_00010000,u_00010000,matched,100.00,1,{SHA},2026-10-25"
    assert lines[3] == f"0x00010020,func_00010020,u_00010000,partial,73.50,3,{SHA},2026-10-25"
    assert lines[4:] == [""]
    assert read_status(path) == sorted(rows, key=lambda r: r.start)


def test_header_only_table_is_valid_and_empty(tmp_path):
    path = tmp_path / "status.csv"
    write_status(path, [])
    assert path.read_text(encoding="utf-8") == f"{STATUS_COMMENT}\n{HEADER}\n"
    assert read_status(path) == []


def test_missing_table_has_no_rows(tmp_path):
    assert read_status(tmp_path / "nope" / "status.csv") == []


GOOD = f"0x00010000,func_00010000,u_00010000,matched,100.00,0,{SHA},2026-10-25"


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (f"{STATUS_COMMENT}\nstart,name,unit,status\n", "header"),
        (f"{HEADER}\n{GOOD}\n", "line 1"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD}\n{GOOD}\n", "line 4: duplicate start 0x00010000"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('matched', 'unmatched')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace(SHA, 'xy' * 32)}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace(SHA, SHA[:-2])}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('2026-10-25', '25/10/2026')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('2026-10-25', '2026-02-30')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('0x00010000', '0x10000')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('100.00', '100')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace('100.00', '99.00')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD.replace(',0,', ',-1,')}\n", "line 3"),
        (f"{STATUS_COMMENT}\n{HEADER}\n{GOOD},extra\n", "line 3"),
        (f"{STATUS_COMMENT}\r\n{HEADER}\r\n{GOOD}\r\n", "LF"),
        (f"{STATUS_COMMENT}\n{HEADER}\n\n{GOOD}\n", "line 3"),
    ],
    ids=["header", "no-comment", "duplicate", "status", "sha-hex", "sha-short", "date-form",
         "date-value", "start-form", "percent-form", "matched-not-100", "attempts", "extra-field",
         "crlf", "blank-line"],  # fmt: skip
)
def test_status_refuses_bad_tables(tmp_path, body, message):
    path = tmp_path / "status.csv"
    path.write_bytes(body.encode("utf-8"))
    with pytest.raises(StatusError, match=message):
        read_status(path)


def test_status_refuses_unsorted_rows(tmp_path):
    later = GOOD.replace("0x00010000,func_00010000", "0x00010020,func_00010020")
    path = tmp_path / "status.csv"
    path.write_bytes(f"{STATUS_COMMENT}\n{HEADER}\n{later}\n{GOOD}\n".encode())
    with pytest.raises(StatusError, match="line 4"):
        read_status(path)


def test_write_refuses_a_duplicate_start_and_writes_nothing(tmp_path):
    path = tmp_path / "status.csv"
    with pytest.raises(StatusError, match="duplicate start 0x00010000"):
        write_status(path, [row(0x10000), row(0x10000, attempts=2)])
    assert not path.exists()


@pytest.mark.parametrize(
    "bad",
    [row(0x10000, status="unmatched"), row(0x10000, sha="xy" * 32), row(0x10000, date="2026-1-5"),
     row(0x10000, percent=99.0), row(0x10000, status=PARTIAL, percent=101.0),
     row(0x10000, attempts=-1), row(0x10000, unit="U-1")],
    ids=["status", "sha", "date", "matched-not-100", "percent", "attempts", "unit"],
)  # fmt: skip
def test_write_refuses_a_row_the_reader_would_refuse(tmp_path, bad):
    path = tmp_path / "status.csv"
    with pytest.raises(StatusError):
        write_status(path, [bad])
    assert not path.exists()


def test_lf_sha256_ignores_crlf():
    text = "int f(void)\n{\n    return 0;\n}\n"
    expected = hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert lf_sha256(text) == expected
    assert lf_sha256(text.replace("\n", "\r\n")) == expected
