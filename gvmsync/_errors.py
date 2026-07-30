# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Custom exception hierarchy for gvmsync."""


class GvmSyncError(Exception):
    """Base exception for all gvmsync errors."""

    def __init__(self, message: str = "") -> None:
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r})"

    def __str__(self) -> str:
        return self.message


class GvmSyncConnectionError(GvmSyncError):
    """Raised when the GMP connection is lost after retries."""


class AuthenticationError(GvmSyncError):
    """Raised when GMP authentication fails."""


class ResourceError(GvmSyncError):
    """Raised when fetching GVM resources fails."""


class GroupError(GvmSyncError):
    """Raised when group creation or lookup fails."""


class PermissionSyncError(GvmSyncError):
    """Raised when permission creation or deletion fails."""


class XmlParseError(GvmSyncError):
    """Raised when XML response parsing fails."""
