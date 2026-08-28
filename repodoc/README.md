# repodoc

A small command-line tool that scans a git repository for leaked secrets,
oversized files, and missing `.gitignore` entries before you commit.

![demo](demo.gif)

## Why I built this

Mature scanners like [Gitleaks](https://github.com/gitleaks/gitleaks) already do
this well and do far more. `repodoc` is a deliberately smaller, focused version:
three checks, a readable report, no configuration. I built it from scratch to
understand how secret detection and basic repo-hygiene checks actually work —
how you walk a tree, tell text from binary, match credential patterns without
drowning in false positives, and parse enough `.gitignore` syntax to know
whether a path is already covered.

It is useful as a fast pre-commit sanity check, and as a codebase that is small
enough to read in one sitting.

## Installation

For now, from a clone:

```bash
pip install -e .
```

Once it is published to PyPI:

```bash
pip install repodoc
```

## Usage

```bash
repodoc scan [path] [--all] [--quiet]
```

- `path` defaults to the current directory.
- `--all` also scans binary files and normally-skipped folders (`node_modules`,
  `.venv`, `dist`, `build`, …).
- `--quiet` prints only the one-line summary.

Example run:

```console
$ repodoc scan .

🩺 repodoc — scanning .
────────────────────────────────────────────
HIGH   config/settings.py:2  Possible hardcoded password found
HIGH   id_rsa:1  Possible private key block found
HIGH   src/aws.txt:1  Possible AWS access key ID found
MEDIUM .env  '.env' is present but not covered by .gitignore
MEDIUM assets/dump.sql  File is 6.0 MB, over the 5 MB limit and not in .gitignore
MEDIUM src/settings.py:3  Possible generic API key found

6 issues found: 3 high, 3 medium, 0 low
```

`HIGH` lines print in red, `MEDIUM` in yellow, `LOW` in blue. A clean repo
prints a green `No issues found ✔`. Non-fatal problems such as permission-denied
files are reported as warnings on stderr and the scan continues.

Exit codes:

| code | meaning |
| ---- | ------- |
| `0`  | no issues found |
| `1`  | one or more issues found |
| `2`  | bad usage or the path does not exist |

so it works as a pre-commit gate.

## What it checks

- **Secrets** — flags lines matching patterns for AWS keys, generic API keys,
  hardcoded passwords, and private-key blocks, across all text files.
- **Large files** — flags files over 5 MB that are not already covered by
  `.gitignore`.
- **`.gitignore` gaps** — flags common generated folders (`node_modules`,
  `__pycache__`, `.env`, `dist`, `build`, `.venv`) that exist in the repo but
  are not ignored.

## Roadmap

This is v0.1. Checks that would fit the same model:

- **Stale TODO / FIXME comments** — flag TODOs older than a chosen age (via
  `git blame`) or ones referencing closed issues.
- **Duplicate dependency versions** — the same package pinned to conflicting
  versions across `requirements*.txt`, `pyproject.toml`, or lockfiles.
- **Committed environment files** — `.env`, `*.pem`, and similar tracked by git
  rather than merely present on disk.

## Development

```bash
pip install -e ".[dev]"
pytest
```
