"""Tests for the three checks, exercised against temporary fixture directories."""

from __future__ import annotations

from pathlib import Path

from repodoc.checks.gitignore import audit_gitignore
from repodoc.checks.large_files import SIZE_LIMIT_BYTES, scan_for_large_files
from repodoc.checks.secrets import scan_directory
from repodoc.scanner import run_all_checks


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_large_file(path: Path, size: int = SIZE_LIMIT_BYTES + 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.seek(size - 1)
        handle.write(b"\0")


# --------------------------------------------------------------------------- #
# secrets
# --------------------------------------------------------------------------- #
def test_secrets_flags_fake_aws_key(tmp_path: Path) -> None:
    _write(tmp_path / "config.txt", "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF\n")

    findings = scan_directory(str(tmp_path))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path == "config.txt"
    assert finding.line_number == 1
    assert finding.severity == "high"
    assert "AWS access key" in finding.message


def test_secrets_flags_private_key_and_password(tmp_path: Path) -> None:
    _write(
        tmp_path / "secrets.env",
        'db_password = "s3cr3t-value"\n'
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "-----END RSA PRIVATE KEY-----\n",
    )

    messages = {f.message for f in scan_directory(str(tmp_path))}

    assert "Possible hardcoded password found" in messages
    assert "Possible private key block found" in messages


def test_secrets_ignores_clean_and_placeholder_files(tmp_path: Path) -> None:
    _write(tmp_path / "ok.py", 'greeting = "hello"\npassword = "changeme"\n')

    assert scan_directory(str(tmp_path)) == []


def test_secrets_skips_binary_files(tmp_path: Path) -> None:
    (tmp_path / "blob.bin").write_bytes(b"AKIA1234567890ABCDEF\x00\x01\x02")

    assert scan_directory(str(tmp_path)) == []


def test_secrets_scan_all_includes_binary_files(tmp_path: Path) -> None:
    (tmp_path / "blob.bin").write_bytes(b"AKIA1234567890ABCDEF\x00\x01\x02")

    findings = scan_directory(str(tmp_path), scan_all=True)

    assert [f.message for f in findings] == ["Possible AWS access key ID found"]


def test_secrets_warns_and_skips_unreadable_file(tmp_path: Path) -> None:
    secret = tmp_path / "locked.txt"
    secret.write_text("AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF\n")
    secret.chmod(0o000)
    warnings: list[str] = []
    try:
        findings = scan_directory(str(tmp_path), warnings=warnings)
    finally:
        secret.chmod(0o644)

    assert findings == []
    assert any("permission denied" in w and "locked.txt" in w for w in warnings)


# --------------------------------------------------------------------------- #
# large files
# --------------------------------------------------------------------------- #
def test_large_files_flags_oversized_file(tmp_path: Path) -> None:
    _make_large_file(tmp_path / "dump.sql")
    _write(tmp_path / "small.txt", "tiny\n")

    findings = scan_for_large_files(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].file_path == "dump.sql"
    assert findings[0].severity == "medium"
    assert "5 MB limit" in findings[0].message


def test_large_files_respects_gitignore(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "*.sql\n")
    _make_large_file(tmp_path / "dump.sql")

    assert scan_for_large_files(str(tmp_path)) == []


def test_large_files_respects_ignored_directory(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "dist/\n")
    _make_large_file(tmp_path / "dist" / "bundle.js")

    assert scan_for_large_files(str(tmp_path)) == []


# --------------------------------------------------------------------------- #
# gitignore audit
# --------------------------------------------------------------------------- #
def test_gitignore_flags_untracked_node_modules(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "dist/\n")
    _write(tmp_path / "node_modules" / "leftpad" / "index.js", "module.exports = 1\n")

    findings = audit_gitignore(str(tmp_path))

    node_modules = [f for f in findings if f.file_path == "node_modules"]
    assert len(node_modules) == 1
    assert node_modules[0].severity == "medium"
    assert "not covered by .gitignore" in node_modules[0].message


def test_gitignore_ok_when_folder_is_covered(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "node_modules/\n__pycache__/\n")
    _write(tmp_path / "node_modules" / "index.js", "x\n")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "m.pyc").write_text("x")

    assert audit_gitignore(str(tmp_path)) == []


def test_gitignore_reports_missing_file(tmp_path: Path) -> None:
    _write(tmp_path / "node_modules" / "index.js", "x\n")

    messages = [f.message for f in audit_gitignore(str(tmp_path))]

    assert any("No .gitignore file found" in m for m in messages)


# --------------------------------------------------------------------------- #
# scanner
# --------------------------------------------------------------------------- #
def test_run_all_checks_combines_findings(tmp_path: Path) -> None:
    _write(tmp_path / ".gitignore", "dist/\n")
    _write(tmp_path / "app.py", "AWS_ACCESS_KEY_ID=AKIA1234567890ABCDEF\n")
    _make_large_file(tmp_path / "big.bin")
    _write(tmp_path / "node_modules" / "index.js", "x\n")

    findings = run_all_checks(str(tmp_path))
    messages = {f.message for f in findings}

    assert "Possible AWS access key ID found" in messages
    assert any("5 MB limit" in m for m in messages)
    assert any("node_modules/" in m for m in messages)
    assert len(findings) >= 3


def test_run_all_checks_on_empty_repo(tmp_path: Path) -> None:
    assert run_all_checks(str(tmp_path)) == []


# --------------------------------------------------------------------------- #
# the committed fixture repo at tests/fixtures/
#
#   config_with_secret.py   one fake API key on line 3
#   big_asset.bin           6 MB dummy file (regenerated by conftest if missing)
#   node_modules/           one placeholder file, NOT covered by .gitignore
#   .gitignore              *.log / dist/ / build/ only
# --------------------------------------------------------------------------- #
FIXTURE_REPO = Path(__file__).parent / "fixtures"


def test_fixture_secrets_finds_exactly_the_api_key() -> None:
    findings = scan_directory(str(FIXTURE_REPO))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path == "config_with_secret.py"
    assert finding.line_number == 3
    assert finding.severity == "medium"
    assert finding.message == "Possible generic API key found"


def test_fixture_large_files_finds_exactly_big_asset() -> None:
    findings = scan_for_large_files(str(FIXTURE_REPO))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path == "big_asset.bin"
    assert finding.severity == "medium"
    assert finding.message == (
        "File is 6.0 MB, over the 5 MB limit and not in .gitignore"
    )


def test_fixture_gitignore_flags_exactly_node_modules() -> None:
    findings = audit_gitignore(str(FIXTURE_REPO))

    assert len(findings) == 1
    finding = findings[0]
    assert finding.file_path == "node_modules"
    assert finding.severity == "medium"
    assert finding.message == (
        "'node_modules/' is present but not covered by .gitignore"
    )


def test_fixture_run_all_checks_exact_findings() -> None:
    findings = run_all_checks(str(FIXTURE_REPO))

    actual = sorted((f.file_path, f.line_number, f.severity, f.message) for f in findings)
    assert actual == [
        (
            "big_asset.bin",
            None,
            "medium",
            "File is 6.0 MB, over the 5 MB limit and not in .gitignore",
        ),
        (
            "config_with_secret.py",
            3,
            "medium",
            "Possible generic API key found",
        ),
        (
            "node_modules",
            None,
            "medium",
            "'node_modules/' is present but not covered by .gitignore",
        ),
    ]
