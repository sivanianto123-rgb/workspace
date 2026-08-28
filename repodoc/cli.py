"""Command-line entry point: `repodoc scan [path]`."""

from __future__ import annotations

import argparse
import os
import sys

from repodoc import __version__
from repodoc.formatter import print_banner, print_report
from repodoc.scanner import run_all_checks

_DESCRIPTION = """\
repodoc scans a git repository for common problems before you commit:

  * leaked secrets   - AWS keys, API keys, hardcoded passwords, private keys
  * oversized files  - files over 5 MB that are not already git-ignored
  * .gitignore gaps  - generated folders (node_modules, __pycache__, .env,
                       dist, build, .venv) present but not ignored
"""

_EPILOG = """\
examples:
  repodoc scan                     scan the current directory
  repodoc scan ../my-project       scan a specific path
  repodoc scan --all               also scan binary files and skipped folders
  repodoc scan --quiet             print only the one-line summary
  repodoc scan ./repo --quiet      combine a path with a flag

exit status:
  0   no issues found
  1   one or more issues found
  2   bad usage or path does not exist
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repodoc",
        description=_DESCRIPTION,
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True, metavar="command")

    scan = subparsers.add_parser(
        "scan",
        help="scan a repository and print a report",
        description="Scan a repository and print a color-coded report.",
        epilog=_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scan.add_argument(
        "path",
        nargs="?",
        default=".",
        help="path to the repository to scan (default: current directory)",
    )
    scan.add_argument(
        "--all",
        dest="scan_all",
        action="store_true",
        help="scan everything, including binary files and normally-skipped "
        "folders such as node_modules and .venv",
    )
    scan.add_argument(
        "--quiet",
        action="store_true",
        help="print only the summary line, not individual findings",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        if not os.path.exists(args.path):
            print(f"repodoc: path does not exist: {args.path}", file=sys.stderr)
            return 2
        if not os.path.isdir(args.path):
            print(f"repodoc: not a directory: {args.path}", file=sys.stderr)
            return 2

        if not args.quiet:
            print_banner(args.path)

        warnings: list[str] = []
        findings = run_all_checks(
            args.path, scan_all=args.scan_all, warnings=warnings
        )
        print_report(findings, quiet=args.quiet, warnings=warnings)
        return 1 if findings else 0

    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
