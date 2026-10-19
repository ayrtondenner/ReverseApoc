"""Ingest: .env parsing, path expansion, Steam/GOG layout search and copying into orig/."""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import write_manifest
from reverseapoc.ingest import (
    IngestError,
    expand_vars,
    find_in_folder,
    game_folders,
    ingest,
    parse_dotenv,
)

FAKE_FILES = {
    "UFOEXE/UFO2P.EXE": b"fake cityscape executable",
    "TACEXE/TACP.EXE": b"fake tactical executable",
    "UFOEXE/SMKP.EXE": b"fake smacker player",
}


def make_game_folder(root: Path, *, steam: bool, skip: tuple[str, ...] = ()) -> Path:
    base = root / "XCOMA" if steam else root
    for rel, content in FAKE_FILES.items():
        if rel in skip:
            continue
        path = base / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


@pytest.fixture
def manifest(tmp_path: Path) -> Path:
    """A manifest whose hashes match FAKE_FILES (paths in the GOG layout)."""
    path = tmp_path / "targets.toml"
    parts = []
    for rel, content in FAKE_FILES.items():
        sub, name = rel.split("/")
        single = tmp_path / f"{name}.toml"
        write_manifest(single, {name: content}, subdir=sub)
        parts.append(single.read_text(encoding="utf-8"))
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


def test_parse_dotenv():
    text = "\n".join(
        [
            "# a comment",
            "",
            r"APOC_STEAM_FOLDER=%ProgramFiles(x86)%\Steam\steamapps\common\XCom Apocalypse",
            r'export APOC_GOG_FOLDER = "C:\Games\X-COM Apocalypse"',
            "SINGLE='a # not a comment'",
            "INLINE=value # trailing comment",
            "HASH=a#b",
            "EQUALS=a=b",
            "EMPTY=",
            "   SPACED  =  padded  ",
            "not an assignment",
        ]
    )
    env = parse_dotenv(text)
    assert env["APOC_STEAM_FOLDER"] == (
        r"%ProgramFiles(x86)%\Steam\steamapps\common\XCom Apocalypse"
    )
    assert env["APOC_GOG_FOLDER"] == r"C:\Games\X-COM Apocalypse"
    assert env["SINGLE"] == "a # not a comment"
    assert env["INLINE"] == "value"
    assert env["HASH"] == "a#b"
    assert env["EQUALS"] == "a=b"
    assert env["EMPTY"] == ""
    assert env["SPACED"] == "padded"
    assert "not an assignment" not in env and len(env) == 8


def test_expand_vars_windows_and_posix_forms():
    env = {"ProgramFiles(x86)": r"C:\Program Files (x86)", "HOME": "/home/me"}
    assert expand_vars(r"%ProgramFiles(x86)%\Steam", env) == r"C:\Program Files (x86)\Steam"
    assert expand_vars("%PROGRAMFILES(X86)%", env) == r"C:\Program Files (x86)"
    assert expand_vars("${HOME}/games", env) == "/home/me/games"
    assert expand_vars("%NOPE%/x ${NOPE}", env) == "%NOPE%/x ${NOPE}"
    assert expand_vars("100% sure", env) == "100% sure"


def test_game_folders_order_and_precedence(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "APOC_STEAM_FOLDER=${BASE}/from-dotenv\nAPOC_GOG_FOLDER=%BASE%/gog\n", encoding="utf-8"
    )
    environ = {"BASE": str(tmp_path)}
    assert game_folders(environ, dotenv) == [
        ("APOC_STEAM_FOLDER", tmp_path / "from-dotenv"),
        ("APOC_GOG_FOLDER", tmp_path / "gog"),
    ]
    environ["APOC_STEAM_FOLDER"] = str(tmp_path / "from-env")  # environment wins over .env
    assert game_folders(environ, dotenv)[0] == ("APOC_STEAM_FOLDER", tmp_path / "from-env")


def test_game_folders_empty_values_and_missing_dotenv(tmp_path):
    environ = {"APOC_STEAM_FOLDER": "  ", "APOC_GOG_FOLDER": str(tmp_path)}
    assert game_folders(environ, tmp_path / "absent.env") == [("APOC_GOG_FOLDER", tmp_path)]
    with pytest.raises(IngestError, match="APOC_STEAM_FOLDER"):
        game_folders({}, tmp_path / "absent.env")


@pytest.mark.parametrize("steam", [True, False], ids=["steam-layout", "gog-layout"])
def test_find_in_folder_layouts(tmp_path, steam):
    root = make_game_folder(tmp_path / "game", steam=steam)
    found = find_in_folder(root, "UFOEXE/UFO2P.EXE")
    assert found is not None and found.read_bytes() == FAKE_FILES["UFOEXE/UFO2P.EXE"]
    assert find_in_folder(root, "UFOEXE/NOPE.EXE") is None
    assert find_in_folder(tmp_path / "does-not-exist", "UFOEXE/UFO2P.EXE") is None


@pytest.mark.parametrize(
    ("on_disk", "wanted"),
    [
        ("xcoma/ufoexe/ufo2p.exe", "UFOEXE/UFO2P.EXE"),  # lower-case folder, upper-case manifest
        ("XCOMA/UFOEXE/UFO2P.EXE", "ufoexe/ufo2p.exe"),  # and the reverse
        ("ufoexe/Ufo2P.Exe", "UFOEXE/UFO2P.EXE"),  # GOG layout, mixed case
        ("Xcoma/UfoExe/UFO2P.exe", "UFOEXE/ufo2p.EXE"),
    ],
)
def test_find_in_folder_ignores_case(tmp_path, on_disk, wanted):
    """Holds on case-sensitive filesystems too (Linux CI, Docker): every path component,
    including the Steam XCOMA/ prefix, is matched by scanning the directory."""
    path = tmp_path / "game" / on_disk
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    found = find_in_folder(tmp_path / "game", wanted)
    assert found is not None and found.read_bytes() == b"x"
    assert found.name.casefold() == "ufo2p.exe"


def test_ingest_copies_from_steam_layout(tmp_path, manifest):
    steam = make_game_folder(tmp_path / "steam", steam=True)
    orig = tmp_path / "orig"
    result = ingest(
        orig_dir=orig,
        manifest=manifest,
        environ={"APOC_STEAM_FOLDER": str(steam)},
        dotenv_path=tmp_path / "absent.env",
    )
    assert result.report.ok, result.report.format()
    assert sorted(p.name for p in orig.iterdir()) == ["SMKP.EXE", "TACP.EXE", "UFO2P.EXE"]
    assert (orig / "TACP.EXE").read_bytes() == FAKE_FILES["TACEXE/TACP.EXE"]
    assert all(c.source.is_relative_to(steam) for c in result.copies)
    # the game folder is only read
    assert (steam / "XCOMA" / "UFOEXE" / "UFO2P.EXE").read_bytes() == FAKE_FILES[
        "UFOEXE/UFO2P.EXE"
    ]
    again = ingest(
        orig_dir=orig,
        manifest=manifest,
        environ={"APOC_STEAM_FOLDER": str(steam)},
        dotenv_path=tmp_path / "absent.env",
    )
    assert [c.action for c in again.copies] == ["unchanged"] * 3


def test_ingest_falls_back_to_gog_per_file_and_reads_dotenv(tmp_path, manifest):
    make_game_folder(tmp_path / "steam", steam=True, skip=("TACEXE/TACP.EXE",))
    gog = make_game_folder(tmp_path / "gog", steam=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "APOC_STEAM_FOLDER=%ROOT%/steam\nAPOC_GOG_FOLDER=${ROOT}/gog\n", encoding="utf-8"
    )
    orig = tmp_path / "orig"
    result = ingest(
        orig_dir=orig, manifest=manifest, environ={"ROOT": str(tmp_path)}, dotenv_path=dotenv
    )
    assert result.report.ok, result.report.format()
    sources = {c.target.name: c.source for c in result.copies}
    assert sources["TACP.EXE"].is_relative_to(gog)
    assert sources["UFO2P.EXE"].is_relative_to(tmp_path / "steam")


def test_ingest_reports_files_found_nowhere(tmp_path, manifest):
    steam = make_game_folder(tmp_path / "steam", steam=True, skip=("UFOEXE/SMKP.EXE",))
    result = ingest(
        orig_dir=tmp_path / "orig",
        manifest=manifest,
        environ={"APOC_STEAM_FOLDER": str(steam)},
        dotenv_path=tmp_path / "absent.env",
    )
    assert [t.name for t in result.not_found] == ["SMKP.EXE"]
    assert not result.report.ok
    assert [r.target.name for r in result.report.missing] == ["SMKP.EXE"]
    assert "SMKP.EXE" in result.format()


def test_ingest_replaces_a_modified_copy(tmp_path, manifest):
    steam = make_game_folder(tmp_path / "steam", steam=True)
    orig = tmp_path / "orig"
    orig.mkdir()
    (orig / "UFO2P.EXE").write_bytes(b"tampered")
    result = ingest(
        orig_dir=orig,
        manifest=manifest,
        environ={"APOC_STEAM_FOLDER": str(steam)},
        dotenv_path=tmp_path / "absent.env",
    )
    actions = {c.target.name: c.action for c in result.copies}
    assert actions["UFO2P.EXE"] == "replaced"
    assert result.report.ok
