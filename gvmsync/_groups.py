# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Phase 2: GVM group management."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from ._errors import GroupError
from ._xml import call_with_retry, parse_response

logger = logging.getLogger(__name__)


def get_existing_groups(gmp: Any) -> dict[str, str]:
    """Fetch all existing GVM groups.

    Args:
        gmp: An authenticated GMP connection.

    Returns:
        Mapping of group name to group ID.
    """
    logger.info("--- Phase 2: Group verification ---")

    response = call_with_retry(gmp.get_groups)
    groups_xml = parse_response(response)
    groups: dict[str, str] = {}

    if groups_xml is not None:
        for group in groups_xml.xpath(".//group"):
            name = group.findtext("name", "")
            gid = group.get("id", "")
            if name and gid:
                groups[name] = gid

    logger.info("Loaded %d existing group(s)", len(groups))
    return groups


def ensure_group(
    gmp: Any,
    group_name: str,
    existing_groups: dict[str, str],
    *,
    dry_run: bool = False,
) -> str | None:
    """Ensure a group exists, creating it if necessary.

    Args:
        gmp: An authenticated GMP connection.
        group_name: Name of the group to ensure.
        existing_groups: Known groups (mutated on creation).
        dry_run: If ``True``, simulate without changes.

    Returns:
        The group ID, or ``None`` on failure.

    Raises:
        GroupError: If group creation fails.
    """
    if group_name in existing_groups:
        logger.info("Group '%s' exists", group_name)
        return existing_groups[group_name]

    if dry_run:
        logger.info(
            "[dry-run] Would create group '%s'",
            group_name,
        )
        return f"dry-run-{group_name}"

    try:
        now = datetime.now(tz=UTC).isoformat()
        response = call_with_retry(
            gmp.create_group,
            name=group_name,
            comment=f"Auto-created by gvmsync - {now}",
        )
        group_xml = parse_response(response)
        if group_xml is None:
            raise GroupError(f"Empty response creating group '{group_name}'")
        group_id = group_xml.get("id", "")
        existing_groups[group_name] = group_id
        logger.info("Created group '%s'", group_name)
        return group_id
    except GroupError:
        raise
    except Exception as exc:
        raise GroupError(
            f"Failed to create group '{group_name}': {exc}"
        ) from exc
