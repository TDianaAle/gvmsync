# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Command-line interface for gvmsync."""

from __future__ import annotations

import argparse
import logging
import os
import sys

from gvm.connections import UnixSocketConnection
from gvm.protocols.gmp import Gmp

from .__version__ import __version__
from ._errors import GvmSyncError
from ._inventory import list_all_resources
from ._sync import run_sync

logger = logging.getLogger("gvmsync")

DEFAULT_SOCKET = "/run/gvmd/gvmd.sock"
DEFAULT_TIMEOUT = 60


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        prog="gvmsync",
        description=(
            "gvmsync - Automated GVM permission "
            "synchronization by project tags."
        ),
        formatter_class=(argparse.RawDescriptionHelpFormatter),
        epilog=(
            "Environment variables:\n"
            "  GVM_ADMIN_USER  "
            "Admin username (alt. to --admin)\n"
            "  GVM_ADMIN_PASS  "
            "Admin password (alt. to --admin-pass)\n"
            "\n"
            "Examples:\n"
            "  gvmsync --admin admin "
            "--admin-pass secret\n"
            "  gvmsync --dry-run --enable-cleanup\n"
            "  gvmsync --all\n"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"gvmsync {__version__}",
    )

    parser.add_argument(
        "--admin",
        metavar="USERNAME",
        help=("GVM admin username (or set GVM_ADMIN_USER)"),
    )
    parser.add_argument(
        "--admin-pass",
        metavar="PASSWORD",
        help=("GVM admin password (or set GVM_ADMIN_PASS)"),
    )
    parser.add_argument(
        "--socket",
        default=DEFAULT_SOCKET,
        metavar="PATH",
        help=(f"Path to GVM Unix socket (default: {DEFAULT_SOCKET})"),
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        metavar="SECONDS",
        help=(f"Connection timeout in seconds (default: {DEFAULT_TIMEOUT})"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate changes without applying them",
    )
    parser.add_argument(
        "--enable-cleanup",
        action="store_true",
        help=("Remove orphaned permissions (garbage collection)"),
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help=("Show inventory of all resources with their tags"),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    return parser


def _setup_logging(*, verbose: bool = False) -> None:
    """Configure the logging subsystem.

    Args:
        verbose: If ``True``, set level to DEBUG.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )


def main() -> int:
    """Entry point for the gvmsync CLI.

    Returns:
        Exit code (0 = success, 1 = error,
        130 = interrupted).
    """
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(verbose=args.verbose)

    admin_user = args.admin or os.environ.get("GVM_ADMIN_USER")
    admin_pass = args.admin_pass or os.environ.get("GVM_ADMIN_PASS")

    if not admin_user:
        logger.error(
            "Admin username required: use --admin or set GVM_ADMIN_USER"
        )
        return 1

    if not admin_pass:
        logger.error(
            "Admin password required: use --admin-pass or set GVM_ADMIN_PASS"
        )
        return 1

    if args.all:
        logger.info(
            "Mode: INVENTORY | User: %s | Socket: %s",
            admin_user,
            args.socket,
        )
    else:
        logger.info(
            "Mode: %s | User: %s | Cleanup: %s | Socket: %s",
            "DRY-RUN" if args.dry_run else "SYNC",
            admin_user,
            "ON" if args.enable_cleanup else "OFF",
            args.socket,
        )

    try:
        conn = UnixSocketConnection(
            path=args.socket,
            timeout=args.timeout,
        )
        with Gmp(connection=conn) as gmp:
            gmp.authenticate(admin_user, admin_pass)
            logger.info("Authenticated as '%s'", admin_user)

            if args.all:
                list_all_resources(gmp)
            else:
                run_sync(
                    gmp,
                    dry_run=args.dry_run,
                    enable_cleanup=args.enable_cleanup,
                )

        return 0

    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130
    except GvmSyncError as exc:
        logger.error("%s", exc)
        return 1
    except Exception as exc:
        logger.error("Unexpected error: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
