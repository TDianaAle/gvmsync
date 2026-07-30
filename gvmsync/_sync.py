# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Orchestrator: sequence phases 1 through 4."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from ._groups import ensure_group, get_existing_groups
from ._permissions import (
    CleanupStats,
    cleanup_orphaned_permissions,
    grant_permissions_for_project,
)
from ._resources import collect_tagged_resources

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Summary of a synchronization run."""

    projects_found: int = 0
    permissions_created: int = 0
    cleanup: CleanupStats | None = None
    elapsed_seconds: float = 0.0


def run_sync(
    gmp: Any,
    *,
    dry_run: bool = False,
    enable_cleanup: bool = False,
) -> SyncResult:
    """Run the full permission synchronization.

    Executes phases 1 through 4 in order:

    1. Extract resources tagged with ``project:*``
    2. Ensure groups exist for each project
    3. Grant required permissions
    4. (Optional) Clean up orphaned permissions

    Args:
        gmp: An authenticated GMP connection.
        dry_run: If ``True``, simulate without changes.
        enable_cleanup: If ``True``, run garbage
            collection in phase 4.

    Returns:
        A summary of the sync run.
    """
    start_time = time.time()
    result = SyncResult()

    all_projects = collect_tagged_resources(gmp)
    result.projects_found = len(all_projects)

    existing_groups = get_existing_groups(gmp)

    if all_projects:
        logger.info("--- Phase 3: Permission configuration ---")

        for project_name, resources in all_projects.items():
            logger.info("Project: %s", project_name)

            group_id = ensure_group(
                gmp,
                project_name,
                existing_groups,
                dry_run=dry_run,
            )
            if not group_id:
                logger.error(
                    "  Skipping project '%s': group creation failed",
                    project_name,
                )
                continue

            count = grant_permissions_for_project(
                gmp,
                group_id,
                resources,
                dry_run=dry_run,
            )
            result.permissions_created += count

    if enable_cleanup:
        result.cleanup = cleanup_orphaned_permissions(
            gmp,
            existing_groups,
            dry_run=dry_run,
        )

    result.elapsed_seconds = time.time() - start_time

    logger.info("--- Summary ---")
    logger.info(
        "Projects: %d | Permissions: %d | Time: %.2fs",
        result.projects_found,
        result.permissions_created,
        result.elapsed_seconds,
    )

    return result
