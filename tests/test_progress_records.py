"""tools/progress.py's committed records: the cold-rebuild verification record (todo
cold-rebuild-record: CI holds no game file, so the owner appends one line per verified commit
to progress/verifications.jsonl after a clean `ninja verify`, and the page shows the newest)
and the hand-off board of functions retired from agent queues (todo long-tail-handoff-board,
config/handoff.csv, read only here). The hashes and tables are made up: no game bytes."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_progress import SHA, T_GAME, U_PARTIAL, load_progress, synthetic_config

UFO_SHA1, TACP_SHA1 = "1" * 40, "2" * 40  # made-up target hashes
COMMIT = "c0ffee" + "0" * 34
IMAGE = "sha256:" + "ab" * 32
HANDOFF_HEADER = "exe,address,reason,retired_on,return_rule\n"


def records_module():
    """progress.py with its records API; a missing name fails the test on this assert."""
    progress = load_progress()
    for name in ("VERIFICATIONS_JSONL", "read_verification", "HANDOFF_CSV", "read_handoff"):
        assert hasattr(progress, name), f"progress.py has no {name}"
    return progress


def checkout(tmp_path: Path) -> Path:
    """A config tree with a made-up targets.toml, inside a repository-shaped directory."""
    config = synthetic_config(tmp_path)
    (config / "targets.toml").write_text(
        f'[[targets]]\nname = "UFO2P.EXE"\nsha1 = "{UFO_SHA1}"\n\n'
        f'[[targets]]\nname = "TACP.EXE"\nsha1 = "{TACP_SHA1}"\n', encoding="utf-8")
    return config


def record(**changes) -> dict:
    line = {"commit": COMMIT, "date": "2026-11-18", "image": IMAGE,
            "sha1": {"UFO2P.EXE": UFO_SHA1, "TACP.EXE": TACP_SHA1}}  # fmt: skip
    line.update(changes)
    return line


def write_records(config: Path, *lines: dict | str) -> Path:
    path = config.parent / "progress" / "verifications.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join((x if isinstance(x, str) else json.dumps(x)) + "\n" for x in lines),
                    encoding="utf-8")  # fmt: skip
    return path


# ---- the cold-rebuild record ----


def test_no_record_file_gives_none(tmp_path):
    progress = records_module()
    assert progress.read_verification(checkout(tmp_path)) is None


def test_the_newest_record_is_the_last_line(tmp_path):
    """Append-only: the last line is the newest record; each EXE's SHA-1 is compared with
    config/targets.toml, and the count of records is kept."""
    progress = records_module()
    config = checkout(tmp_path)
    older = record(commit="b" * 40, date="2026-11-17")
    write_records(config, older, "", record(sha1={"UFO2P.EXE": UFO_SHA1, "TACP.EXE": "3" * 40}))
    found = progress.read_verification(config)
    assert (found.commit, found.date, found.image, found.records) == (
        COMMIT, "2026-11-18", IMAGE, 2)
    assert found.sha1 == (("UFO2P.EXE", UFO_SHA1, True), ("TACP.EXE", "3" * 40, False))


@pytest.mark.parametrize("line, problem", [
    ("{not json", "not JSON"),
    (json.dumps([1]), "not an object"),
    (json.dumps(record(commit="abc")), "commit"),
    (json.dumps(record(date="2026-13-01")), "date"),
    (json.dumps(record(image="latest")), "image"),
    (json.dumps(record(sha1={"UFO2P.EXE": UFO_SHA1})), "sha1"),
    (json.dumps(record(sha1={"UFO2P.EXE": UFO_SHA1, "TACP.EXE": "X" * 40})), "sha1"),
    (json.dumps({k: v for k, v in record().items() if k != "image"}), "image"),
    (json.dumps(record(note="extra")), "note"),
])  # fmt: skip
def test_a_malformed_record_names_its_line(tmp_path, line, problem):
    progress = records_module()
    config = checkout(tmp_path)
    path = write_records(config, record(), line)
    where = re.escape(f"{path}: line 2: ")
    with pytest.raises(progress.ProgressError, match=rf"{where}.*{problem}"):
        progress.read_verification(config)


def test_main_shows_the_newest_record(tmp_path):
    """progress.json's "verification" holds the newest record with each EXE's comparison; the
    page states it under the commit line, linked to the verified commit."""
    progress = records_module()
    config = checkout(tmp_path)
    write_records(config, record())
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out), "--commit", SHA]) == 0
    doc = json.loads((out / "progress.json").read_text(encoding="utf-8"))["verification"]
    assert doc == {"commit": COMMIT, "date": "2026-11-18", "image": IMAGE, "records": 1,
                   "sha1": {"UFO2P.EXE": {"sha1": UFO_SHA1, "identical": True},
                            "TACP.EXE": {"sha1": TACP_SHA1, "identical": True}}}  # fmt: skip
    page = (out / "index.html").read_text(encoding="utf-8")
    line = (f'<p class="meta">Cold rebuild verified at commit <a href="https://github.com/'
            f'ayrtondenner/ReverseApoc/commit/{COMMIT}">c0ffee0</a> on 2026-11-18 in image '
            f"sha256:abababababab: UFO2P.EXE SHA-1 {UFO_SHA1[:12]} identical to the original, "
            f"TACP.EXE SHA-1 {TACP_SHA1[:12]} identical to the original.</p>")  # fmt: skip
    assert line in page
    assert page.index("Updated from commit") < page.index(line) < page.index("UFO2P.EXE</h2>")
    bare = tmp_path / "bare"
    assert progress.main(["--config", str(synthetic_config(bare)), "--out", str(bare / "o")]) == 0
    assert json.loads((bare / "o" / "progress.json").read_text())["verification"] is None
    assert "Cold rebuild" not in (bare / "o" / "index.html").read_text(encoding="utf-8")


# ---- the hand-off board ----


def write_handoff(config: Path, text: str) -> None:
    (config / "handoff.csv").write_text(text, encoding="utf-8")


def test_an_absent_or_empty_board_lists_nothing(tmp_path):
    progress = records_module()
    config = checkout(tmp_path)
    derived = progress.derive(config)
    assert progress.read_handoff(config, derived) == ()
    write_handoff(config, HANDOFF_HEADER)
    assert progress.read_handoff(config, derived) == ()
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    assert json.loads((out / "progress.json").read_text(encoding="utf-8"))["handoff"] == []
    assert 'class="handoff"' not in (out / "index.html").read_text(encoding="utf-8")


def test_the_board_lists_its_rows_with_their_best_percent(tmp_path):
    """Each row joined with its function: name, status and best percent from status.csv, in
    the board's order, with its reason, date and return rule, in progress.json and on the
    page."""
    progress = records_module()
    config = checkout(tmp_path)
    write_handoff(config, HANDOFF_HEADER
                  + f"ufo2p,0x{U_PARTIAL.start:08X},5 models failed; best 50%,2026-11-18,"
                    "a new compiler flag or a human hint\n"
                  + f"tacp,0x{T_GAME.start:08X},too long,2026-11-17,never by agents\n")
    out = tmp_path / "out"
    assert progress.main(["--config", str(config), "--out", str(out)]) == 0
    board = json.loads((out / "progress.json").read_text(encoding="utf-8"))["handoff"]
    assert board == [
        {"exe": "ufo2p", "address": f"0x{U_PARTIAL.start:08X}", "name": U_PARTIAL.name,
         "status": "partial", "best_percent": 50.0, "reason": "5 models failed; best 50%",
         "retired_on": "2026-11-18", "return_rule": "a new compiler flag or a human hint"},
        {"exe": "tacp", "address": f"0x{T_GAME.start:08X}", "name": T_GAME.name,
         "status": "unmatched", "best_percent": 0.0, "reason": "too long",
         "retired_on": "2026-11-17", "return_rule": "never by agents"},
    ]  # fmt: skip
    page = (out / "index.html").read_text(encoding="utf-8")
    section = re.search(r'<section class="handoff" aria-labelledby="handoff">(.*?)</section>',
                        page, re.S)[1]  # fmt: skip
    assert '<h2 id="handoff">Hand-off board</h2>' in section
    assert page.index("Hand-off board") < page.index("<h2>The mosaic</h2>")
    rows = re.findall(r"<tr><td>(.*?)</td></tr>", section)
    assert rows[0] == (f"{U_PARTIAL.name}</td><td>UFO2P.EXE</td><td>50%</td><td>2026-11-18</td>"
                       "<td>5 models failed; best 50%</td><td>a new compiler flag or a human "
                       "hint")  # fmt: skip


@pytest.mark.parametrize("text, problem", [
    ("exe,address,reason\n", "header"),
    (HANDOFF_HEADER + "dos,0x00010000,r,2026-11-18,x\n", "exe"),
    (HANDOFF_HEADER + "ufo2p,10000,r,2026-11-18,x\n", "address"),
    (HANDOFF_HEADER + "ufo2p,0x00010000,r,18/11/2026,x\n", "retired_on"),
    (HANDOFF_HEADER + "ufo2p,0x00099990,r,2026-11-18,x\n", "no game or thunk row"),
    (HANDOFF_HEADER + "ufo2p,0x00010000,r,2026-11-18,x\nufo2p,0x00010000,r,2026-11-18,x\n",
     "twice"),
])  # fmt: skip
def test_a_malformed_board_is_refused(tmp_path, text, problem):
    progress = records_module()
    config = checkout(tmp_path)
    write_handoff(config, text)
    with pytest.raises(progress.ProgressError, match=problem):
        progress.read_handoff(config, progress.derive(config))
