"""`reverseapoc` command line: ingest, check-orig, parse-le."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .ingest import IngestError, ingest
from .le import LE, LEError, format_summary
from .targets import DEFAULT_MANIFEST, DEFAULT_ORIG, ManifestError, check_orig


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (IngestError, LEError, ManifestError, OSError) as exc:
        print(f"reverseapoc {args.command}: error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
