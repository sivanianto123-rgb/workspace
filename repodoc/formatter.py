"""Render a list of Finding objects as a color-coded terminal report using rich."""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from repodoc.finding import Finding

_SEVERITY_STYLE = {"high": "bold red", "medium": "yellow", "low": "blue"}
_SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def print_banner(path: str, console: Console | None = None) -> None:
    """Print the colored startup header: 🩺 repodoc — scanning <path>."""
    console = console or Console()
    console.print()
    console.print(
        Text.assemble(
            ("🩺 repodoc", "bold cyan"),
            (" — scanning ", "dim"),
            (str(path), "bold"),
        ),
        soft_wrap=True,
    )
    console.print(Text("─" * 44, style="dim"))


def _print_warnings(warnings: list[str] | None) -> None:
    if not warnings:
        return
    # Warnings go to stderr so --quiet stdout stays exactly one line.
    err = Console(stderr=True)
    for message in warnings:
        err.print(Text.assemble(("⚠ ", "yellow"), (message, "dim yellow")))


def print_report(
    findings: list[Finding],
    console: Console | None = None,
    *,
    quiet: bool = False,
    warnings: list[str] | None = None,
) -> None:
    """Print a color-coded report: red=high, yellow=medium, blue=low, plus a summary.

    Findings are always ordered by severity (high first), then path, then line.
    With ``quiet=True`` only the final summary line is printed to stdout.
    """
    console = console or Console()
    _print_warnings(warnings)

    if not findings:
        console.print(Text("No issues found ", style="bold green") + Text("✔"))
        return

    ordered = sorted(
        findings,
        key=lambda f: (
            _SEVERITY_ORDER.get(f.severity, 99),
            f.file_path,
            f.line_number or 0,
        ),
    )

    counts = {"high": 0, "medium": 0, "low": 0}
    for finding in ordered:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
        if quiet:
            continue

        style = _SEVERITY_STYLE.get(finding.severity, "white")
        location = finding.file_path
        if finding.line_number is not None:
            location += f":{finding.line_number}"

        line = Text()
        line.append(f"{finding.severity.upper():<6} ", style=style)
        line.append(location, style="bold")
        line.append("  ")
        line.append(finding.message)
        console.print(line)

    total = len(ordered)
    summary = (
        f"{total} issue{'s' if total != 1 else ''} found: "
        f"{counts['high']} high, {counts['medium']} medium, {counts['low']} low"
    )
    if not quiet:
        console.print()
    console.print(Text(summary, style="bold"))
