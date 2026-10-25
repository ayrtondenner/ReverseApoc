"""report.json in objdiff's report shape (RPT-04, D-28, D-49): every key is a report.proto field
name, every Measures field is filled at report, category and unit level, u64 fields are decimal
strings (pbjson's proto3 JSON mapping) and u32/float fields numbers, and the combined
matched_code_percent is progress.json's combined percent. recomp.fyi's ingestion is private, so
the shape is pinned to the proto, not to its reader."""

from __future__ import annotations

import json

import pytest

from reverseapoc.status import MATCHED, StatusRow, status_path, write_status
from test_progress import (
    CONFIG,
    SHA,
    T_GAME,
    U_MATCHED,
    U_PARTIAL,
    U_THUNK,
    U_UNMATCHED,
    load_progress,
    size,
    synthetic_config,
)

# from objdiff-core/protos/report.proto, 2026-10-24
REPORT_FIELDS = frozenset({"measures", "units", "version", "categories"})
MEASURES_FIELDS = frozenset({
    "fuzzy_match_percent", "total_code", "matched_code", "matched_code_percent", "total_data",
    "matched_data", "matched_data_percent", "total_functions", "matched_functions",
    "matched_functions_percent", "complete_code", "complete_code_percent", "complete_data",
    "complete_data_percent", "total_units", "complete_units",
})  # fmt: skip
CATEGORY_FIELDS = frozenset({"id", "name", "measures"})
UNIT_FIELDS = frozenset({"name", "measures", "sections", "functions", "metadata"})
UNIT_METADATA_FIELDS = frozenset({"complete", "module_name", "module_id", "source_path",
                                  "progress_categories", "auto_generated"})  # fmt: skip
ITEM_FIELDS = frozenset({"name", "size", "fuzzy_match_percent", "metadata", "address"})
ITEM_METADATA_FIELDS = frozenset({"demangled_name", "virtual_address"})
REPORT_VERSION = 2  # objdiff-core/src/bindings/report.rs REPORT_VERSION
# The proto3 u64 fields, which pbjson writes as JSON strings.
MEASURES_U64 = frozenset({"total_code", "matched_code", "total_data", "matched_data",
                          "complete_code", "complete_data"})  # fmt: skip
ITEM_U64 = frozenset({"size", "address"})
CATEGORIES = ("ufo2p", "tacp")


def report(config) -> dict:
    progress = load_progress()
    assert hasattr(progress, "build_report"), "progress.py has no build_report"
    return progress.build_report(progress.derive(config))


def every_measures(doc: dict):
    """(where, measures) at report, category and unit level."""
    yield "report", doc["measures"]
    for category in doc["categories"]:
        yield f"category {category['id']}", category["measures"]
    for unit in doc["units"]:
        yield f"unit {unit['name']}", unit["measures"]


@pytest.fixture(scope="module")
def committed() -> dict:
    return report(CONFIG)


def test_report_field_names_are_proto_names(committed):
    assert set(committed) == REPORT_FIELDS
    assert committed["version"] == REPORT_VERSION
    for category in committed["categories"]:
        assert set(category) <= CATEGORY_FIELDS, category["id"]
    for unit in committed["units"]:
        assert set(unit) <= UNIT_FIELDS, unit["name"]
        assert set(unit.get("metadata", {})) <= UNIT_METADATA_FIELDS, unit["name"]
        for item in unit.get("functions", []) + unit.get("sections", []):
            assert set(item) <= ITEM_FIELDS, (unit["name"], item)
            assert set(item.get("metadata", {})) <= ITEM_METADATA_FIELDS, item


def test_report_every_measure_filled(committed):
    for where, measures in every_measures(committed):
        assert set(measures) == MEASURES_FIELDS, where


def test_report_u64_are_strings(committed):
    for where, measures in every_measures(committed):
        for name, value in measures.items():
            if name in MEASURES_U64:
                assert isinstance(value, str) and value.isdecimal(), (where, name, value)
            else:
                assert isinstance(value, int | float) and not isinstance(value, bool), (where, name)
    for unit in committed["units"]:
        for item in unit.get("functions", []):
            for name in ITEM_U64 & set(item):
                assert isinstance(item[name], str) and item[name].isdecimal(), (unit["name"], name)
            assert isinstance(item["fuzzy_match_percent"], int | float)


def test_report_percent_equals_progress(committed):
    progress = load_progress()
    derived = progress.derive(CONFIG)
    assert committed["measures"]["matched_code_percent"] == derived.combined.percent
    assert [c["id"] for c in committed["categories"]] == list(CATEGORIES)
    for category in committed["categories"]:
        exe = derived.exe(category["id"])
        assert category["measures"]["matched_code_percent"] == exe.totals.percent
        assert category["measures"]["total_code"] == str(exe.totals.denominator_bytes)
    names = [unit["name"] for unit in committed["units"]]
    for exe in CATEGORIES:
        assert f"{exe}/uncovered" in names
    assert len(names) == len(set(names))


def test_report_units_are_the_units_with_game_rows(committed):
    """One unit per units.csv unit holding game/thunk rows, tagged with its EXE's category, plus
    one <exe>/uncovered unit; the runtime library is in no unit (D-26)."""
    progress = load_progress()
    derived = progress.derive(CONFIG)
    for exe in derived.exes:
        expected = sorted({f.unit for f in exe.functions})
        listed = [u["name"].split("/", 1)[1] for u in committed["units"]
                  if u["name"].startswith(f"{exe.stem}/") and u["name"] != f"{exe.stem}/uncovered"]
        assert listed == expected
    for unit in committed["units"]:
        assert unit["metadata"]["progress_categories"] == [unit["name"].split("/", 1)[0]]


def test_report_counts_on_synthetic_csvs(tmp_path):
    """Fuzzy percent weighted by size (matched 100, partial its best_percent, others 0), zero
    totals give 100.0 (objdiff's rule), the uncovered unit holds the gap."""
    doc = report(synthetic_config(tmp_path))
    ufo = next(c for c in doc["categories"] if c["id"] == "ufo2p")["measures"]
    code = size(U_MATCHED) + size(U_PARTIAL) + size(U_UNMATCHED) + size(U_THUNK)  # 228
    assert ufo["total_code"] == str(code + 16) and ufo["matched_code"] == "16"
    assert ufo["matched_code_percent"] == round(100 * 16 / 244, 4)
    assert ufo["fuzzy_match_percent"] == round((16 * 100 + 32 * 50) / 244, 4) == 13.1148
    assert (ufo["total_functions"], ufo["matched_functions"]) == (4, 1)
    assert ufo["matched_functions_percent"] == 25.0
    assert (ufo["total_data"], ufo["matched_data"]) == ("0", "0")
    assert ufo["matched_data_percent"] == 100.0
    assert (ufo["complete_data"], ufo["complete_data_percent"]) == ("0", 100.0)
    assert (ufo["total_units"], ufo["complete_units"]) == (2, 0)
    assert (ufo["complete_code"], ufo["complete_code_percent"]) == ("0", 0.0)
    gap = next(u for u in doc["units"] if u["name"] == "ufo2p/uncovered")["measures"]
    assert (gap["total_code"], gap["matched_code"], gap["total_functions"]) == ("16", "0", 0)
    assert gap["matched_code_percent"] == 0.0
    assert doc["measures"]["total_code"] == str(code + 16 + size(T_GAME))


def test_report_complete_units(tmp_path):
    """A unit is complete when every game/thunk row of it is matched."""
    config = synthetic_config(tmp_path)
    write_status(status_path(config, "tacp"), [
        StatusRow(T_GAME.start, T_GAME.name, T_GAME.unit, MATCHED, 100.0, 0, SHA, "2026-10-25")])
    doc = report(config)
    tacp = next(u for u in doc["units"] if u["name"] == "tacp/u_00020000")
    assert tacp["metadata"]["complete"] is True
    measures = next(c for c in doc["categories"] if c["id"] == "tacp")["measures"]
    assert (measures["complete_units"], measures["complete_code"]) == (1, "32")
    assert measures["complete_code_percent"] == 100.0
    assert measures["matched_code_percent"] == 100.0
    assert doc["measures"]["complete_units"] == 1


def test_report_is_byte_stable(tmp_path):
    progress = load_progress()
    config = synthetic_config(tmp_path)
    for name in ("a.json", "b.json"):
        progress.write_report(progress.derive(config), tmp_path / name)
    data = (tmp_path / "a.json").read_bytes()
    assert data == (tmp_path / "b.json").read_bytes() and data.endswith(b"}\n")
    assert json.loads(data)["version"] == REPORT_VERSION
