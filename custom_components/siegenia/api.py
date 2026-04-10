"""Compatibility wrapper for the reusable Siegenia client package."""

from .siegenia_client import AuthenticationError, SiegeniaClient, SiegeniaError

__all__ = ["AuthenticationError", "SiegeniaClient", "SiegeniaError"]
