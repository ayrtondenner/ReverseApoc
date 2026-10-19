"""Watcom media layer: manifest, fetch (fake opener), install (synthetic ISO) and key-file check."""

from __future__ import annotations

import dataclasses
import hashlib
import http.client
import io
import zlib
from pathlib import Path

import pytest

from isoimage import build_iso
from reverseapoc import watcom
from reverseapoc.iso9660 import ISO9660, ISOError
from reverseapoc.targets import ManifestError
from reverseapoc.watcom import (
    KeyFile,
    WatcomError,
    WatcomMedia,
    check_version,
    check_watcom,
    fetch_media,
    fetch_watcom,
    install_version,
    load_watcom_manifest,
    select,
)


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def _sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _media(
    data: bytes,
    version: str = "9.0",
    file: str = "Test.iso",
    key_files=(),
    skip_dirs=(),
    note: str = "",
) -> WatcomMedia:
    return WatcomMedia(
        skip_dirs=skip_dirs,
        note=note,
        version=version,
        item="Item",
        file=file,
        size=len(data),
        md5=_md5(data),
        sha1=_sha1(data),
        crc32=zlib.crc32(data),
        key_files=tuple(key_files),
    )


GOOD = (
    '[[media]]\nversion = "1.0"\nitem = "I"\nfile = "a.iso"\nsize = 3\n'
    'md5 = "{md5}"\nsha1 = "{sha1}"\n'
).format(md5="0" * 32, sha1="0" * 40)


# 1. default manifest -------------------------------------------------------------------------


def test_default_manifest_parses():
    manifest = load_watcom_manifest()
    assert list(manifest) == ["10.5", "10.6", "11.0", "11.0a", "11.0b"]
    m = manifest["10.5"]
    assert (m.item, m.file, m.size, m.crc32) == (
        "Watcom_C_10.5", "Watcom_C++_10.5.iso", 515213312, 0x6BE5E3F6,
    )  # fmt: skip
    assert m.md5 == "3200b70ba399c840775e9bfa2fe19875"
    assert m.sha1 == "0722e7494647cd5e9a66bd106aa80a620f7ee999"
    m = manifest["10.6"]
    assert (m.item, m.file, m.size, m.crc32) == (
        "Watcom_C_10.6", "Watcom_C++_10.6.iso", 664373248, 0xE154C2DE,
    )  # fmt: skip
    assert m.md5 == "5a252e04e3a9fd5c802d1d3fd33f458e"
    assert m.sha1 == "211f4e7acecf89cf8af26e12099e1aec5a255f65"
    m = manifest["11.0"]
    assert (m.item, m.file, m.size, m.crc32) == (
        "Watcom_C_11.0", "Watcom_C++_11.0.iso", 669603840, 0xC4FF34AB,
    )  # fmt: skip
    assert m.md5 == "aa6ee011958dd0371f95ac0bbaa50026"
    assert m.sha1 == "1708a29f7209b9d29aff18aba8923a0ddd5d97cc"
    m = manifest["11.0a"]
    assert (m.item, m.file, m.size, m.crc32) == (
        "watcom-c-cpp-compilers-collection", "watcom-11.0a/WatcomC11a.iso", 670785536, None,
    )  # fmt: skip
    assert m.md5 == "a72d0cdd049a9119b46ad70846590a28"
    assert m.sha1 == "8361779a2c7fb395eedff82d4f6207a819292f87"
    m = manifest["11.0b"]
    assert (m.item, m.file, m.size, m.crc32) == (
        "watcom-c-cpp-compilers-collection", "watcom-11.0b/WATCOM_C11B.iso", 649111552, None,
    )  # fmt: skip
    assert m.md5 == "28e3660f972860c77cf3804eb2e0177d"
    assert m.sha1 == "da67b5b249357b120e20d8580043ead319f2a91b"


def test_urls_and_local_name():
    manifest = load_watcom_manifest()
    assert manifest["10.6"].url() == (
        "https://archive.org/download/Watcom_C_10.6/Watcom_C%2B%2B_10.6.iso"
    )
    assert manifest["11.0a"].url() == (
        "https://archive.org/download/watcom-c-cpp-compilers-collection/"
        "watcom-11.0a/WatcomC11a.iso"
    )
    assert manifest["11.0a"].local_name == "WatcomC11a.iso"
    assert manifest["10.6"].local_name == "Watcom_C++_10.6.iso"


# 2. invalid manifests ------------------------------------------------------------------------

_KF = '[[media.key_files]]\npath = "BINW/X.EXE"\nsize = 1\nmd5 = "{m}"\nsha1 = "{s}"\n'


@pytest.mark.parametrize(
    "text",
    [
        "title = 'nothing'\n",
        GOOD.replace("0" * 40, "0" * 39),
        GOOD.replace("size = 3", "size = -1"),
        GOOD + GOOD,
        GOOD + _KF.format(m="zz", s="0" * 40),
        GOOD + _KF.replace('path = "BINW/X.EXE"\n', "").format(m="0" * 32, s="0" * 40),
        GOOD + _KF.format(m="0" * 32, s="0" * 40) + "known_bad = 'yes'\n",
    ],
    ids=["no-media", "bad-sha1", "neg-size", "duplicate", "bad-md5-key", "no-path", "bad-flag"],
)
def test_invalid_manifests(tmp_path, text):
    path = tmp_path / "w.toml"
    path.write_text(text)
    with pytest.raises(ManifestError):
        load_watcom_manifest(path)


def test_key_files_parse(tmp_path):
    path = tmp_path / "w.toml"
    path.write_text(
        GOOD
        + _KF.format(m="0" * 32, s="0" * 40)
        + 'known_bad = true\nnote = "broken"\n'
    )
    kf = load_watcom_manifest(path)["1.0"].key_files[0]
    assert (kf.path, kf.size, kf.known_bad, kf.note) == ("BINW/X.EXE", 1, True, "broken")
    assert kf.as_target().name == "BINW/X.EXE"


# 3. select -----------------------------------------------------------------------------------


def test_select():
    manifest = load_watcom_manifest()
    assert [m.version for m in select(manifest, [])] == list(manifest)
    assert [m.version for m in select(manifest, ["10.6"])] == ["10.6"]
    with pytest.raises(ManifestError, match="10.5.*10.6"):
        select(manifest, ["9.9"])


# 4. fetch ------------------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, body: bytes, headers: dict | None = None):
        self._io = io.BytesIO(body)
        self.headers = {} if headers is None else headers

    def read(self, n: int = -1) -> bytes:
        return self._io.read(n)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeOpener:
    def __init__(self, body: bytes, headers: dict | None = None):
        self.body, self.headers, self.calls = body, headers, []

    def __call__(self, req, timeout=None):
        self.calls.append((req, timeout))
        return FakeResponse(self.body, self.headers)


def test_fetch_downloads_then_is_present(tmp_path):
    data = b"x" * 5000
    media = _media(data)
    opener = FakeOpener(data, {"Content-Length": str(len(data))})
    r = fetch_media(media, tmp_path / "m", opener=opener, chunk=1000)
    assert r.action == "downloaded" and not r.problems
    assert (tmp_path / "m" / "Test.iso").read_bytes() == data
    assert not (tmp_path / "m" / "Test.iso.part").exists()
    req, timeout = opener.calls[0]
    assert req.full_url == "https://archive.org/download/Item/Test.iso"
    assert req.get_header("User-agent") == "reverseapoc" and timeout == 60
    r = fetch_media(media, tmp_path / "m", opener=opener)
    assert r.action == "present" and len(opener.calls) == 1


def test_fetch_uses_basename_for_subpath(tmp_path):
    data = b"x" * 10
    media = _media(data, file="sub/dir/Name.iso")
    opener = FakeOpener(data)
    fetch_media(media, tmp_path, opener=opener)
    assert (tmp_path / "Name.iso").read_bytes() == data
    assert opener.calls[0][0].full_url.endswith("/Item/sub/dir/Name.iso")


def test_fetch_hash_mismatch_keeps_part(tmp_path):
    data = b"x" * 100
    media = _media(data)
    r = fetch_media(media, tmp_path, opener=FakeOpener(b"y" * 100))
    assert r.action == "mismatch"
    assert any("md5" in p for p in r.problems)
    assert (tmp_path / "Test.iso.part").exists() and not (tmp_path / "Test.iso").exists()


def test_fetch_content_length_mismatch(tmp_path):
    data = b"x" * 100
    r = fetch_media(_media(data), tmp_path, opener=FakeOpener(data, {"Content-Length": "99"}))
    assert r.action == "mismatch" and r.problems
    assert list(tmp_path.iterdir()) == []


def test_fetch_oversize_body(tmp_path):
    data = b"x" * 100
    r = fetch_media(_media(data), tmp_path, opener=FakeOpener(data + b"x" * 500), chunk=64)
    assert r.action == "mismatch"
    assert not (tmp_path / "Test.iso").exists()
    assert not (tmp_path / "Test.iso.part").exists()


class RaisingResponse(FakeResponse):
    def read(self, n: int = -1) -> bytes:
        raise http.client.IncompleteRead(b"")


def test_fetch_incomplete_read_is_mismatch(tmp_path):
    def opener(req, timeout=None):
        return RaisingResponse(b"")

    r = fetch_media(_media(b"x" * 10), tmp_path, opener=opener)
    assert r.action == "mismatch" and r.problems[0].startswith("download failed")


def test_fetch_opener_oserror_is_mismatch(tmp_path):
    def opener(req, timeout=None):
        raise OSError("network down")

    r = fetch_media(_media(b"x" * 10), tmp_path, opener=opener)
    assert r.action == "mismatch" and r.problems[0].startswith("download failed")
    assert not (tmp_path / "Test.iso").exists()


def test_fetch_crc32_mismatch_is_mismatch(tmp_path):
    data = b"x" * 100
    media = dataclasses.replace(_media(data), crc32=zlib.crc32(data) ^ 1)
    r = fetch_media(media, tmp_path, opener=FakeOpener(data))
    assert r.action == "mismatch"
    assert any(p.startswith("crc32: expected") for p in r.problems)
    assert not (tmp_path / "Test.iso").exists()


def test_install_crc32_mismatch_is_rejected(tmp_path):
    media, media_dir, install_dir = _iso_media(tmp_path)
    media = dataclasses.replace(media, crc32=(media.crc32 or 0) ^ 1)
    with pytest.raises(WatcomError, match="crc32: expected"):
        install_version(media, media_dir, install_dir)


def test_fetch_bad_base_url_is_mismatch(tmp_path):
    data = b"x" * 10
    r = fetch_media(_media(data), tmp_path, base="foo", opener=FakeOpener(data))
    assert r.action == "mismatch" and r.problems[0].startswith("download failed")


def test_fetch_redownloads_corrupt_dest(tmp_path):
    data = b"x" * 100
    (tmp_path / "Test.iso").write_bytes(b"corrupt")
    opener = FakeOpener(data)
    r = fetch_media(_media(data), tmp_path, opener=opener)
    assert r.action == "downloaded" and len(opener.calls) == 1
    assert (tmp_path / "Test.iso").read_bytes() == data


def test_fetch_mismatch_leaves_existing_dest(tmp_path):
    data = b"x" * 100
    (tmp_path / "Test.iso").write_bytes(b"corrupt")
    r = fetch_media(_media(data), tmp_path, opener=FakeOpener(b"y" * 100))
    assert r.action == "mismatch"
    assert (tmp_path / "Test.iso").read_bytes() == b"corrupt"


def test_fetch_watcom_report(tmp_path):
    data = b"x" * 50
    manifest = tmp_path / "w.toml"
    manifest.write_text(
        '[[media]]\nversion = "9.0"\nitem = "Item"\nfile = "Test.iso"\n'
        f'size = {len(data)}\nmd5 = "{_md5(data)}"\nsha1 = "{_sha1(data)}"\n'
    )
    report = fetch_watcom(
        ["9.0"], manifest=manifest, media_dir=tmp_path / "m", opener=FakeOpener(data)
    )
    assert report.ok
    text = report.format()
    assert "DOWNLOADED" in text and "9.0" in text
    bad = fetch_watcom(
        [], manifest=manifest, media_dir=tmp_path / "m2", opener=FakeOpener(b"y" * 50)
    )
    assert not bad.ok and "MISMATCH" in bad.format()


# 5. install ----------------------------------------------------------------------------------

TREE = {"BINW/WCC386.EXE": b"compiler", "H/STDIO.H": b"#include", "README.TXT": b"hi"}


def _iso_media(tmp_path: Path, version: str = "9.0") -> tuple[WatcomMedia, Path, Path]:
    image = build_iso(TREE)
    media = _media(image, version=version)
    media_dir, install_dir = tmp_path / "media", tmp_path / "install"
    media_dir.mkdir()
    (media_dir / media.local_name).write_bytes(image)
    return media, media_dir, install_dir


def test_install_extracts_and_replaces(tmp_path):
    media, media_dir, install_dir = _iso_media(tmp_path)
    install_version(media, media_dir, install_dir)
    assert (install_dir / "9.0" / "BINW" / "WCC386.EXE").read_bytes() == b"compiler"
    assert (install_dir / "9.0" / "H" / "STDIO.H").read_bytes() == b"#include"
    with pytest.raises(WatcomError, match="--force"):
        install_version(media, media_dir, install_dir)
    (install_dir / "9.0" / "stale.txt").write_text("old")
    install_version(media, media_dir, install_dir, force=True)
    assert not (install_dir / "9.0" / "stale.txt").exists()
    assert (install_dir / "9.0" / "README.TXT").read_bytes() == b"hi"
    assert [p.name for p in install_dir.iterdir()] == ["9.0"]


def test_install_removes_stale_partial(tmp_path):
    media, media_dir, install_dir = _iso_media(tmp_path)
    (install_dir / ".9.0.partial").mkdir(parents=True)
    (install_dir / ".9.0.partial" / "junk").write_text("x")
    install_version(media, media_dir, install_dir)
    assert not (install_dir / "9.0" / "junk").exists()
    assert not (install_dir / ".9.0.partial").exists()


def test_install_missing_iso(tmp_path):
    media, media_dir, install_dir = _iso_media(tmp_path)
    (media_dir / media.local_name).unlink()
    with pytest.raises(WatcomError, match="fetch-watcom 9.0"):
        install_version(media, media_dir, install_dir)


def test_install_wrong_hash(tmp_path):
    media, media_dir, install_dir = _iso_media(tmp_path)
    path = media_dir / media.local_name
    path.write_bytes(path.read_bytes()[:-1] + b"Z")
    with pytest.raises(WatcomError, match="fetch-watcom"):
        install_version(media, media_dir, install_dir)
    assert not install_dir.exists() or not any(install_dir.iterdir())


def test_install_extract_failure_is_wrapped_and_leaves_install_intact(tmp_path, monkeypatch):
    media, media_dir, install_dir = _iso_media(tmp_path)
    install_version(media, media_dir, install_dir)

    def boom(iso, dest, **kw):
        (Path(dest) / "half").mkdir(parents=True)
        raise ISOError("bad sector")

    monkeypatch.setattr(watcom, "extract_all", boom)
    with pytest.raises(WatcomError, match=r"9\.0.*bad sector"):
        install_version(media, media_dir, install_dir, force=True)
    assert [p.name for p in install_dir.iterdir()] == ["9.0"]
    assert (install_dir / "9.0" / "README.TXT").read_bytes() == b"hi"


def _flaky_replace(monkeypatch, failures, exc=PermissionError):
    """Patch os.replace (as used by watcom) to fail `failures` times, then work; record sleeps."""
    real, calls, sleeps = watcom.os.replace, [], []

    def replace(src, dst):
        calls.append((src, dst))
        if failures is None or len(calls) <= failures:
            raise exc(5, "Access denied")
        real(src, dst)

    monkeypatch.setattr(watcom.os, "replace", replace)
    monkeypatch.setattr(watcom.time, "sleep", sleeps.append)
    return calls, sleeps


def test_install_retries_transient_permission_error(tmp_path, monkeypatch):
    media, media_dir, install_dir = _iso_media(tmp_path)
    calls, sleeps = _flaky_replace(monkeypatch, 2)
    install_version(media, media_dir, install_dir)
    assert len(calls) == 3 and len(sleeps) == 2
    assert (install_dir / "9.0" / "BINW" / "WCC386.EXE").read_bytes() == b"compiler"
    assert [p.name for p in install_dir.iterdir()] == ["9.0"]


def test_install_gives_up_after_bounded_retries(tmp_path, monkeypatch):
    media, media_dir, install_dir = _iso_media(tmp_path)
    calls, sleeps = _flaky_replace(monkeypatch, None)
    with pytest.raises(WatcomError, match=r"9\.0.*re-run"):
        install_version(media, media_dir, install_dir)
    assert len(calls) == 8 and len(sleeps) == 7
    assert not (install_dir / ".9.0.partial").exists()
    assert not (install_dir / "9.0").exists()


def test_install_does_not_retry_other_oserror(tmp_path, monkeypatch):
    media, media_dir, install_dir = _iso_media(tmp_path)
    calls, sleeps = _flaky_replace(monkeypatch, None, exc=OSError)
    with pytest.raises(OSError):
        install_version(media, media_dir, install_dir)
    assert len(calls) == 1 and sleeps == []
    assert not (install_dir / ".9.0.partial").exists()


def test_install_skips_listed_corrupt_directory(tmp_path):
    image = bytearray(build_iso({"SUB/BAD/X.TXT": b"x", "SUB/OK.TXT": b"ok"}))
    iso_path = tmp_path / "t.iso"
    iso_path.write_bytes(bytes(image))
    with ISO9660.open(iso_path) as iso:
        extent = next(e.extent for e in iso.walk() if e.path == "SUB/BAD")
    garbage = bytes([0x97] + [(7 * i) % 251 for i in range(2047)])
    image[extent * 2048 : (extent + 1) * 2048] = garbage
    media_dir, install_dir = tmp_path / "media", tmp_path / "install"
    media_dir.mkdir()
    (media_dir / "Test.iso").write_bytes(bytes(image))
    media = _media(bytes(image), skip_dirs=("SUB/BAD",))
    with pytest.raises(WatcomError, match="SUB/BAD"):
        install_version(_media(bytes(image)), media_dir, install_dir)
    install_version(media, media_dir, install_dir)
    assert (install_dir / "9.0" / "SUB" / "OK.TXT").read_bytes() == b"ok"
    assert not (install_dir / "9.0" / "SUB" / "BAD").exists()


def test_media_fields_skip_dirs_and_note(tmp_path):
    path = tmp_path / "w.toml"
    path.write_text(GOOD + 'skip_dirs = ["A/B"]\nnote = "damaged"\n')
    m = load_watcom_manifest(path)["1.0"]
    assert m.skip_dirs == ("A/B",) and m.note == "damaged"
    for bad in ('skip_dirs = "A/B"\n', 'skip_dirs = [""]\n', "skip_dirs = [1]\n", "note = 3\n"):
        path.write_text(GOOD + bad)
        with pytest.raises(ManifestError):
            load_watcom_manifest(path)


def test_default_11_0b_skips_damaged_sample_dir():
    m = load_watcom_manifest()["11.0b"]
    assert m.skip_dirs == ("SAMPLES/WIN/DATACTL/WIN16",)
    assert "sector (353)" in m.note
    assert load_watcom_manifest()["10.5"].skip_dirs == ()


def test_check_format_prints_media_note(tmp_path):
    media = _media(b"x", note="damaged sector")
    assert "damaged sector" in check_version(media, tmp_path).format()


# 6. check ------------------------------------------------------------------------------------


def _kf(path: str, data: bytes, **kw) -> KeyFile:
    return KeyFile(path, len(data), _md5(data), _sha1(data), **kw)


def _checked(tmp_path, key_files, files: dict[str, bytes]):
    media = _media(b"x", key_files=key_files)
    root = tmp_path / "install" / media.version
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    return media, tmp_path / "install"


def test_check_statuses(tmp_path):
    kfs = [
        _kf("A.EXE", b"aaa"),
        _kf("B.EXE", b"bbb"),
        _kf("C.EXE", b"ccc"),
        _kf("D.EXE", b"ddd", known_bad=True, note="shipped broken"),
    ]
    media, install_dir = _checked(
        tmp_path, kfs, {"A.EXE": b"aaa", "B.EXE": b"BBB", "D.EXE": b"ddd"}
    )
    vc = check_version(media, install_dir)
    assert [r.status for r in vc.results] == ["ok", "mismatch", "missing", "known-bad"]
    assert vc.ok is False


def test_check_known_bad_does_not_fail(tmp_path):
    kfs = [_kf("A.EXE", b"aaa"), _kf("D.EXE", b"ddd", known_bad=True, note="shipped broken")]
    media, install_dir = _checked(tmp_path, kfs, {"A.EXE": b"aaa", "D.EXE": b"ddd"})
    vc = check_version(media, install_dir)
    assert vc.ok
    text = vc.format()
    assert "KNOWN BAD D.EXE" in text and "shipped broken" in text
    assert "1 ok, 0 mismatched, 0 missing, 1 known bad" in text


def test_check_known_bad_with_other_hash_is_mismatch(tmp_path):
    kfs = [_kf("D.EXE", b"ddd", known_bad=True)]
    media, install_dir = _checked(tmp_path, kfs, {"D.EXE": b"zzz"})
    assert check_version(media, install_dir).results[0].status == "mismatch"


def test_check_missing_version_dir(tmp_path):
    media = _media(b"x", key_files=[_kf("A.EXE", b"a")])
    vc = check_version(media, tmp_path / "nowhere")
    assert [r.status for r in vc.results] == ["missing"] and not vc.ok


def test_check_no_key_files_not_ok(tmp_path):
    media = _media(b"x")
    vc = check_version(media, tmp_path)
    assert not vc.ok and "no key files recorded" in vc.format()


def test_check_watcom_report(tmp_path):
    manifest = tmp_path / "w.toml"
    data = b"aaa"
    manifest.write_text(
        '[[media]]\nversion = "9.0"\nitem = "I"\nfile = "a.iso"\nsize = 3\n'
        f'md5 = "{"0" * 32}"\nsha1 = "{"0" * 40}"\n'
        '[[media.key_files]]\npath = "A.EXE"\nsize = 3\n'
        f'md5 = "{_md5(data)}"\nsha1 = "{_sha1(data)}"\n'
    )
    install = tmp_path / "install"
    (install / "9.0").mkdir(parents=True)
    (install / "9.0" / "A.EXE").write_bytes(data)
    report = check_watcom(["9.0"], manifest=manifest, install_dir=install)
    assert report.ok and "OK" in report.format()
    (install / "9.0" / "A.EXE").write_bytes(b"bad")
    report = check_watcom([], manifest=manifest, install_dir=install)
    assert not report.ok and "MISMATCH" in report.format()


def test_defaults_are_under_repo():
    assert watcom.DEFAULT_WATCOM_MANIFEST.name == "watcom.toml"
    assert watcom.DEFAULT_MEDIA.parts[-2:] == ("third_party", "watcom-media")
    assert watcom.DEFAULT_INSTALL.parts[-2:] == ("third_party", "watcom")
    assert "proprietary" in watcom.MEDIA_NOTICE


# 8. pinned key files in the default manifest -------------------------------------------------


def _key(version: str, path: str) -> KeyFile:
    return next(k for k in load_watcom_manifest()[version].key_files if k.path == path)


def test_default_manifest_pins_key_files():
    for version, media in load_watcom_manifest().items():
        assert len(media.key_files) >= 8, version


def test_default_manifest_pinned_values():
    assert _key("10.6", "BINW/WCC386.EXE").size == 567698
    k = _key("10.5", "BINW/WCC386.EXE")
    assert k.size == 65536
    assert k.known_bad is True
    assert _key("11.0", "BINNT/WCCD386.DLL").size == 659968
    assert _key("10.6", "BINW/WCC386.EXE").sha1 == "183433f959d6071fd00ea1917effd9085066d227"
    assert _key("10.6", "LIB386/DOS/CLIB3R.LIB").sha1 == "57250829673b7849ce70bf0e288e61ff98231de7"
