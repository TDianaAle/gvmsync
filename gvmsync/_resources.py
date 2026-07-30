# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Phase 1: extract GVM resources tagged with ``project:*``."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from lxml.etree import _Element as Element

from ._errors import ResourceError
from ._xml import call_with_retry, parse_response

logger = logging.getLogger(__name__)

RESOURCE_TYPES: tuple[str, ...] = ("scanner", "task", "report")

PERMISSION_CONFIG: dict[str, list[str]] = {
    "scanner": ["get_scanners"],
    "task": ["get_tasks", "start_task", "stop_task"],
    "report": ["get_reports"],
}


@dataclass(frozen=True)
class TaggedResource:
    """A GVM resource associated with a project tag."""

    resource_id: str
    name: str
    resource_type: str


@dataclass
class ProjectResources:
    """All tagged resources belonging to a single project."""

    project_name: str
    scanners: list[TaggedResource] = field(
        default_factory=list,
    )
    tasks: list[TaggedResource] = field(
        default_factory=list,
    )
    reports: list[TaggedResource] = field(
        default_factory=list,
    )

    def resources_for_type(
        self,
        resource_type: str,
    ) -> list[TaggedResource]:
        """Return resources list for *resource_type*.

        Args:
            resource_type: One of ``scanner``, ``task``,
                ``report``.

        Returns:
            The matching resource list.
        """
        mapping: dict[str, list[TaggedResource]] = {
            "scanner": self.scanners,
            "task": self.tasks,
            "report": self.reports,
        }
        return mapping.get(resource_type, [])


def extract_project_names(
    element: Element,
) -> list[str]:
    """Extract project names from ``project:*`` tags.

    Args:
        element: An lxml Element representing a GVM resource.

    Returns:
        List of unique project names found in the tags.
    """
    projects: list[str] = []
    for tag in element.xpath(".//tag"):
        tag_name = tag.findtext("name", "")
        if tag_name.startswith("project:"):
            project = tag_name.split("project:", 1)[1]
            if project and project not in projects:
                projects.append(project)
    return projects


def extract_all_tags(element: Element) -> list[str]:
    """Extract all tag names from a resource element.

    Args:
        element: An lxml Element representing a GVM resource.

    Returns:
        List of unique tag names.
    """
    tags: list[str] = []
    for tag in element.xpath(".//tag"):
        tag_name = tag.findtext("name", "")
        if tag_name and tag_name not in tags:
            tags.append(tag_name)
    return tags


def get_owner(element: Element) -> str:
    """Extract the owner name from a resource element.

    Args:
        element: An lxml Element representing a GVM resource.

    Returns:
        Owner name, or ``"Unknown"`` if not found.
    """
    owner_elem = element.find(".//owner")
    if owner_elem is not None:
        name = owner_elem.findtext("name", "")
        if name:
            return name
    return "Unknown"


def _get_resources_by_type(
    gmp: Any,
    resource_type: str,
) -> dict[str, list[TaggedResource]]:
    """Fetch resources of a given type and group by project.

    Args:
        gmp: An authenticated GMP connection.
        resource_type: One of ``scanner``, ``task``, ``report``.

    Returns:
        Mapping of project name to list of tagged resources.

    Raises:
        ResourceError: If fetching resources fails.
    """
    get_funcs: dict[str, Any] = {
        "scanner": gmp.get_scanners,
        "task": gmp.get_tasks,
        "report": gmp.get_reports,
    }

    func = get_funcs.get(resource_type)
    if func is None:
        return {}

    try:
        response = call_with_retry(func, details=True)
    except Exception as exc:
        raise ResourceError(
            f"Failed to retrieve {resource_type}s: {exc}"
        ) from exc

    resources_xml = parse_response(response)
    if resources_xml is None:
        return {}

    projects_resources: dict[str, list[TaggedResource]] = {}
    all_elems = resources_xml.xpath(f".//{resource_type}")
    tagged_count = 0

    for elem in all_elems:
        projects = extract_project_names(elem)
        if not projects:
            continue

        tagged_count += 1
        res_id = elem.get("id", "")
        res_name = elem.findtext("name", "unknown")
        resource = TaggedResource(
            resource_id=res_id,
            name=res_name,
            resource_type=resource_type,
        )

        for project in projects:
            if project not in projects_resources:
                projects_resources[project] = []
            if not any(
                r.resource_id == res_id for r in projects_resources[project]
            ):
                projects_resources[project].append(resource)

    logger.info(
        "Found %d/%d %s(s) with project tags",
        tagged_count,
        len(all_elems),
        resource_type,
    )
    return projects_resources


def collect_tagged_resources(
    gmp: Any,
) -> dict[str, ProjectResources]:
    """Collect all resources with ``project:*`` tags.

    Scans scanners, tasks, and reports, groups them by
    project name.

    Args:
        gmp: An authenticated GMP connection.

    Returns:
        Mapping of project name to its resources.
    """
    logger.info("--- Phase 1: Resource extraction ---")

    all_projects: dict[str, ProjectResources] = {}

    for resource_type in RESOURCE_TYPES:
        logger.info(
            "Extracting %ss with project:* tags...",
            resource_type,
        )
        projects_data = _get_resources_by_type(gmp, resource_type)

        for project, resources in projects_data.items():
            if project not in all_projects:
                all_projects[project] = ProjectResources(
                    project_name=project,
                )

            target = all_projects[project].resources_for_type(
                resource_type,
            )
            target.extend(resources)

    if not all_projects:
        logger.warning("No resources with project:* tags found")
    else:
        logger.info("Discovered %d project(s)", len(all_projects))

    return all_projects
