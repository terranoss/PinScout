from __future__ import annotations

__version__ = "1.0.0"


def get_app_version() -> str:
    """Return the application semantic version (e.g. 'v1.0.0')."""
    return f"v{__version__}"


def get_git_short_sha() -> str:
    """Deprecated: alias to get_app_version for backwards compatibility."""
    return get_app_version()

