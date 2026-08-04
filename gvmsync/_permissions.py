# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Phases 3 and 4: permission granting and cleanup."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from ._resources import (
    PERMISSION_CONFIG,
    ProjectResources,
    TaggedResource,
    extract_project_names,
)
from ._xml import call_with_retry, parse_response

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PermissionRecord:
    """A permission entry linked to a resource."""

    permission_id: str
    permission_name: str
    resource_id: str
    resource_name: str
    resource_type: str


@dataclass
class CleanupStats:
    """Statistics from the garbage collection phase."""

    scanned: int = 0
    orphaned_deleted: int = 0
    orphaned_untagged: int = 0
    removed: int = 0


# ------------------------------------------------------------------
# Phase 3: permission granting
# ------------------------------------------------------------------


def _permission_exists(
    gmp: Any,
    group_id: str,
    resource_id: str,
    permission_name: str,
) -> bool:
    """Check whether a specific permission already exists.

    Args:
        gmp: An authenticated GMP connection.
        group_id: The subject group ID.
        resource_id: The target resource ID.
        permission_name: The GMP permission name.

    Returns:
        ``True`` if the permission exists.
    """
    try:
        response = call_with_retry(
            gmp.get_permissions,
            filter_string=(
                f"subject_uuid={group_id} and "
                f"resource_uuid={resource_id} and "
                f'name="{permission_name}"'
            ),
        )
        pxml = parse_response(response)
        if pxml is None:
            return False
        return len(pxml.xpath(".//permission")) > 0
    except Exception:
        return False


def _grant_permission(
    gmp: Any,
    group_id: str,
    resource: TaggedResource,
    permission_name: str,
    *,
    dry_run: bool = False,
) -> bool:
    """Grant a single permission if it does not exist.

    Args:
        gmp: An authenticated GMP connection.
        group_id: The subject group ID.
        resource: The target resource.
        permission_name: The GMP permission name.
        dry_run: If ``True``, simulate without changes.

    Returns:
        ``True`` if a new permission was granted.
    """
    if _permission_exists(
        gmp,
        group_id,
        resource.resource_id,
        permission_name,
    ):
        return False

    if dry_run:
        logger.info(
            "  [dry-run] Would grant '%s' on '%s'",
            permission_name,
            resource.name,
        )
        return True

    try:
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC).isoformat()
        call_with_retry(
            gmp.create_permission,
            name=permission_name,
            subject_id=group_id,
            subject_type="group",
            resource_id=resource.resource_id,
            resource_type=resource.resource_type,
            comment=f"gvmsync - {now}",
        )
        return True
    except Exception as exc:
        logger.error(
            "  Failed to grant '%s' on '%s': %s",
            permission_name,
            resource.name,
            exc,
        )
        return False


def grant_permissions_for_project(
    gmp: Any,
    group_id: str,
    resources: ProjectResources,
    *,
    dry_run: bool = False,
) -> int:
    """Grant all required permissions for a project.

    Args:
        gmp: An authenticated GMP connection.
        group_id: The group ID to grant permissions to.
        resources: The project's tagged resources.
        dry_run: If ``True``, simulate without changes.

    Returns:
        Number of permissions newly granted.
    """
    total = 0

    for res_type, perms in PERMISSION_CONFIG.items():
        res_list = resources.resources_for_type(res_type)
        if not res_list:
            continue

        logger.info(
            "  Configuring %d %s(s)...",
            len(res_list),
            res_type,
        )

        for resource in res_list:
            for perm_name in perms:
                if _grant_permission(
                    gmp,
                    group_id,
                    resource,
                    perm_name,
                    dry_run=dry_run,
                ):
                    total += 1
                    logger.info(
                        "    Granted '%s' on '%s'",
                        perm_name,
                        resource.name,
                    )

    if total > 0:
        logger.info("  Configured %d permission(s)", total)

    return total


# ------------------------------------------------------------------
# Phase 4: garbage collection
# ------------------------------------------------------------------


def _get_group_permissions(
    gmp: Any,
    group_id: str,
) -> list[PermissionRecord]:
    """Get all permissions assigned to a group.

    Args:
        gmp: An authenticated GMP connection.
        group_id: The group ID.

    Returns:
        List of permission records.
    """
    try:
        response = call_with_retry(
            gmp.get_permissions,
            filter_string=f"subject_uuid={group_id}",
        )
        pxml = parse_response(response)
        if pxml is None:
            return []

        records: list[PermissionRecord] = []
        for perm in pxml.xpath(".//permission"):
            resource_elem = perm.find(".//resource")
            if resource_elem is None:
                continue

            type_elem = resource_elem.find("type")
            records.append(
                PermissionRecord(
                    permission_id=perm.get("id", ""),
                    permission_name=perm.findtext("name", ""),
                    resource_id=resource_elem.get("id", ""),
                    resource_name=resource_elem.findtext("name", "unknown"),
                    resource_type=(
                        type_elem.text if type_elem is not None else ""
                    ),
                ),
            )
        return records
    except Exception:
        return []


def _resource_still_tagged(
    gmp: Any,
    resource_type: str,
    resource_id: str,
    expected_project: str,
) -> tuple[bool, str]:
    """Check if a resource still carries the project tag.

    Args:
        gmp: An authenticated GMP connection.
        resource_type: The GVM resource type.
        resource_id: The resource ID.
        expected_project: The project name to look for.

    Returns:
        Tuple of (still_valid, reason).
    """
    get_funcs: dict[str, Any] = {
        "scanner": gmp.get_scanners,
        "task": gmp.get_tasks,
        "report": gmp.get_reports,
    }

    func = get_funcs.get(resource_type)
    if func is None:
        return (True, "unknown_type")

    try:
        response = call_with_retry(
            func,
            filter_string=f"uuid={resource_id}",
            details=True,
        )
        rxml = parse_response(response)
        if rxml is None:
            return (False, "deleted")

        # direct children only: GMP nests same-named elements
        # inside a detailed resource (see select_resources)
        xpath = f"./{resource_type}[@id='{resource_id}']"
        elem = rxml.find(xpath)
        if elem is None:
            return (False, "deleted")

        projects = extract_project_names(elem)
        if expected_project in projects:
            return (True, "ok")
        return (False, "tag_removed")
    except Exception:
        return (True, "error")


def cleanup_orphaned_permissions(
    gmp: Any,
    existing_groups: dict[str, str],
    *,
    dry_run: bool = False,
) -> CleanupStats:
    """Remove permissions for deleted or untagged resources.

    Args:
        gmp: An authenticated GMP connection.
        existing_groups: Mapping of group name to ID.
        dry_run: If ``True``, simulate without changes.

    Returns:
        Cleanup statistics.
    """
    logger.info("--- Phase 4: Garbage collection ---")

    stats = CleanupStats()

    for group_name, group_id in existing_groups.items():
        logger.info("Checking group '%s'...", group_name)
        permissions = _get_group_permissions(gmp, group_id)

        if not permissions:
            continue

        stats.scanned += len(permissions)

        for perm in permissions:
            still_valid, reason = _resource_still_tagged(
                gmp,
                perm.resource_type,
                perm.resource_id,
                group_name,
            )

            if still_valid:
                continue

            if reason == "deleted":
                stats.orphaned_deleted += 1
                logger.info(
                    "  Resource '%s' deleted",
                    perm.resource_name,
                )
            elif reason == "tag_removed":
                stats.orphaned_untagged += 1
                logger.info(
                    "  Tag removed from '%s'",
                    perm.resource_name,
                )

            if dry_run:
                logger.info(
                    "    [dry-run] Would remove permission '%s'",
                    perm.permission_name,
                )
                stats.removed += 1
                continue

            try:
                gmp.delete_permission(
                    permission_id=perm.permission_id,
                )
                stats.removed += 1
                logger.info(
                    "    Removed permission '%s'",
                    perm.permission_name,
                )
            except Exception as exc:
                logger.error(
                    "    Failed to remove '%s': %s",
                    perm.permission_name,
                    exc,
                )

    logger.info(
        "Cleanup: scanned=%d, orphaned=%d, removed=%d",
        stats.scanned,
        stats.orphaned_deleted + stats.orphaned_untagged,
        stats.removed,
    )
    return stats
