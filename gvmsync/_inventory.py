# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Inventory mode: list all GVM resources with their tags."""

from __future__ import annotations

import logging
from typing import Any

from ._resources import (
    RESOURCE_TYPES,
    extract_all_tags,
    extract_project_names,
    get_owner,
)
from ._xml import call_with_retry, parse_response

logger = logging.getLogger(__name__)

_GET_FUNCS_ATTR: dict[str, str] = {
    "scanner": "get_scanners",
    "task": "get_tasks",
    "report": "get_reports",
}


def list_all_resources(gmp: Any) -> None:
    """List all GVM resources with their tags.

    Displays a complete inventory of scanners, tasks, and
    reports, showing which ones carry ``project:*`` tags
    and will be synced.

    Args:
        gmp: An authenticated GMP connection.
    """
    logger.info("--- Inventory: all resources ---")

    total_resources = 0
    total_tagged = 0
    total_project_tagged = 0

    for res_type in RESOURCE_TYPES:
        func_name = _GET_FUNCS_ATTR.get(res_type)
        if func_name is None:
            continue

        func = getattr(gmp, func_name, None)
        if func is None:
            continue

        logger.info("")
        logger.info("== %sS ==", res_type.upper())

        try:
            response = call_with_retry(func, details=True)
            rxml = parse_response(response)
            if rxml is None:
                logger.warning("Could not parse %ss", res_type)
                continue

            elements = rxml.xpath(f".//{res_type}")
            if not elements:
                logger.info("No %ss found", res_type)
                continue

            logger.info(
                "Found %d %s(s)",
                len(elements),
                res_type,
            )

            for elem in elements:
                total_resources += 1
                res_id = elem.get("id", "")
                res_name = elem.findtext("name", "unknown")
                owner = get_owner(elem)
                all_tags = extract_all_tags(elem)
                project_tags = extract_project_names(elem)

                display_name = (
                    res_name[:50] + "..." if len(res_name) > 50 else res_name
                )

                if all_tags:
                    total_tagged += 1
                    tag_str = ", ".join(all_tags)

                    if project_tags:
                        total_project_tagged += 1
                        logger.info(
                            "  [SYNC] %s  id=%s  owner=%s  tags=%s",
                            display_name,
                            res_id,
                            owner,
                            tag_str,
                        )
                    else:
                        logger.info(
                            "  [----] %s  "
                            "id=%s  owner=%s  "
                            "tags=%s  "
                            "(no project:* tag)",
                            display_name,
                            res_id,
                            owner,
                            tag_str,
                        )
                else:
                    logger.info(
                        "  [----] %s  id=%s  owner=%s  (no tags)",
                        display_name,
                        res_id,
                        owner,
                    )

        except Exception as exc:
            logger.error(
                "Failed to retrieve %ss: %s",
                res_type,
                exc,
            )

    logger.info("")
    logger.info("--- Inventory summary ---")
    logger.info("Total resources: %d", total_resources)
    logger.info("With any tags: %d", total_tagged)
    logger.info(
        "With project:* tags (will sync): %d",
        total_project_tagged,
    )
    logger.info(
        "Without tags: %d",
        total_resources - total_tagged,
    )
    logger.info("")
    logger.info("Legend:")
    logger.info("  [SYNC] = has project:* tags, will be synced")
    logger.info("  [----] = no project:* tags, will NOT be synced")
