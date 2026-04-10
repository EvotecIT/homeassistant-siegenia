"""Regression checks for the standalone Siegenia Python package."""

from siegenia_client import SiegeniaClient
from siegenia_client.client import SiegeniaClient as ClientFromModule


def test_public_package_exports_client() -> None:
    assert SiegeniaClient is ClientFromModule
