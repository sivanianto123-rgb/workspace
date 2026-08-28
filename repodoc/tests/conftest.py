"""Shared test setup.

``tests/fixtures/big_asset.bin`` is a 6 MB dummy file used by the large-file
check tests. A blob that size is awkward to keep in version control, so this
fixture regenerates it (as a sparse file) whenever it is missing or the wrong
size, keeping the suite runnable from a fresh checkout.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_REPO = Path(__file__).parent / "fixtures"
BIG_ASSET = FIXTURE_REPO / "big_asset.bin"
BIG_ASSET_SIZE = 6 * 1024 * 1024  # 6 MB, comfortably over the 5 MB limit


@pytest.fixture(scope="session", autouse=True)
def ensure_big_asset() -> None:
    if not BIG_ASSET.exists() or BIG_ASSET.stat().st_size != BIG_ASSET_SIZE:
        BIG_ASSET.parent.mkdir(parents=True, exist_ok=True)
        with open(BIG_ASSET, "wb") as handle:
            handle.seek(BIG_ASSET_SIZE - 1)
            handle.write(b"\0")
