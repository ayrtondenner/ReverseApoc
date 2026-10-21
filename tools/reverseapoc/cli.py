"""`reverseapoc` command line: ingest, check-orig, parse-le, rebuild, fetch-watcom,
install-watcom, check-watcom."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ingest import IngestError, ingest
from .iso9660 import ISOError
from .le import LE, LEError, format_summary
from .splice import DEFAULT_OUT, rebuild
from .targets import DEFAULT_MANIFEST, DEFAULT_ORIG, ManifestError, check_orig
from .watcom import (
    ARCHIVE_BASE,
    DEFAULT_INSTALL,
    DEFAULT_MEDIA,
    DEFAULT_WATCOM_MANIFEST,
    MEDIA_NOTICE,
    WatcomError,
    check_watcom,
    fetch_watcom,
    install_version,
    load_watcom_manifest,
    select,
)


def _cmd_ingest(args: argparse.Namespace) -> int:
    result = ingest(orig_dir=args.orig, manifest=args.manifest, dotenv_path=args.env_file)
    print(result.format())
    return 0 if result.report.ok else 1


def _cmd_check_orig(args: argparse.Namespace) -> int:
    report = check_orig(args.orig, args.manifest)
    print(report.format())
    return 0 if report.ok else 1


def _cmd_parse_le(args: argparse.Namespace) -> int:
    summary = LE(args.file).summary()
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(format_summary(summary))
    return 0


def _cmd_rebuild(args: argparse.Namespace) -> int:
    try:
        report = rebuild(args.orig, args.out, args.manifest, exe=args.exe)
    except (LEError, ManifestError, OSError):
        # A failure before any target (manifest, --exe, --out): with --json, stdout is still a
        # list, and main() prints the error line (WR-04).
        if args.json:
            print("[]")
        raise
    if args.json:
        print(json.dumps(report.to_json(), indent=2))
    else:
        print(report.format())
    return 0 if report.ok else 1


# ---- Watcom media: fetch-watcom, install-watcom, check-watcom ----


def _cmd_fetch_watcom(args: argparse.Namespace) -> int:
    print(MEDIA_NOTICE, file=sys.stderr)
    report = fetch_watcom(
        args.versions, manifest=args.manifest, media_dir=args.media, base=args.base_url
    )
    print(report.format())
    return 0 if report.ok else 1


def _cmd_install_watcom(args: argparse.Namespace) -> int:
    chosen = select(load_watcom_manifest(args.manifest), args.versions)
    ok = True
    for media in chosen:
        try:
            result = install_version(media, args.media, args.dest, force=args.force)
        except WatcomError as exc:
            print(f"reverseapoc install-watcom: {media.version}: {exc}", file=sys.stderr)
            ok = False
            continue
        print(result.format())
        ok = ok and result.ok
    return 0 if ok else 1


def _cmd_check_watcom(args: argparse.Namespace) -> int:
    report = check_watcom(args.versions, manifest=args.manifest, install_dir=args.dest)
    print(report.format())
    return 0 if report.ok else 1


def _add_watcom_commands(sub: argparse._SubParsersAction) -> None:
    def common(p: argparse.ArgumentParser, *, media: bool, dest: bool) -> None:
        default = "default: %(default)s"
        p.add_argument("versions", nargs="*", metavar="VERSION", help="default: all")
        p.add_argument("--manifest", type=Path, default=DEFAULT_WATCOM_MANIFEST, help=default)
        if media:
            p.add_argument("--media", type=Path, default=DEFAULT_MEDIA, help=default)
        if dest:
            p.add_argument("--dest", type=Path, default=DEFAULT_INSTALL, help=default)

    p = sub.add_parser(
        "fetch-watcom",
        help="download the original Watcom CD images from the Internet Archive into "
        "third_party/watcom-media/ and verify them",
    )
    common(p, media=True, dest=False)
    p.add_argument("--base-url", default=ARCHIVE_BASE, help="default: %(default)s")
    p.set_defaults(func=_cmd_fetch_watcom)

    p = sub.add_parser(
        "install-watcom",
        help="extract verified Watcom CD images into third_party/watcom/<version>/ and check "
        "their key files",
    )
    common(p, media=True, dest=True)
    p.add_argument("--force", action="store_true", help="replace an existing installation")
    p.set_defaults(func=_cmd_install_watcom)

    p = sub.add_parser(
        "check-watcom", help="verify the key files of installed Watcom versions"
    )
    common(p, media=False, dest=True)
    p.set_defaults(func=_cmd_check_watcom)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reverseapoc", description="ReverseApoc tooling for the X-COM Apocalypse executables."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def orig_and_manifest(p: argparse.ArgumentParser) -> None:
        p.add_argument("--orig", type=Path, default=DEFAULT_ORIG, help="default: %(default)s")
        p.add_argument(
            "--manifest", type=Path, default=DEFAULT_MANIFEST, help="default: %(default)s"
        )

    p = sub.add_parser(
        "ingest",
        help="copy the executables from your game folder into orig/ and verify them",
        description="Reads APOC_STEAM_FOLDER (then APOC_GOG_FOLDER) from the environment or "
        ".env; the game folder is only read.",
    )
    orig_and_manifest(p)
    p.add_argument("--env-file", type=Path, default=None, help="default: <repo>/.env")
    p.set_defaults(func=_cmd_ingest)

    p = sub.add_parser("check-orig", help="verify orig/ against config/targets.toml")
    orig_and_manifest(p)
    p.set_defaults(func=_cmd_check_orig)

    p = sub.add_parser("parse-le", help="print the LE layout of an executable")
    p.add_argument("file", type=Path)
    p.add_argument("--json", action="store_true", help="print the summary as JSON")
    p.set_defaults(func=_cmd_parse_le)

    p = sub.add_parser(
        "rebuild",
        help="rebuild every target (or only --exe NAME) from orig/ into build/ and check its "
        "SHA-1 against config/targets.toml",
    )
    orig_and_manifest(p)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT, help="default: %(default)s")
    p.add_argument(
        "--exe",
        metavar="NAME",
        help="rebuild only this target from the manifest (case-insensitive)",
    )
    p.add_argument("--json", action="store_true", help="print the results as JSON")
    p.set_defaults(func=_cmd_rebuild)

    _add_watcom_commands(sub)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (IngestError, LEError, ManifestError, ISOError, WatcomError, OSError) as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
