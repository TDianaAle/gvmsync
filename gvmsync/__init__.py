# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""gvmsync - Automated permission synchronization for GVM by tags."""

from .__version__ import __version__

__all__ = ("__version__", "get_version")


def get_version() -> str:
    """Return the current version of gvmsync."""
    return __version__
