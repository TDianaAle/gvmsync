# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Seed a GVM instance with test data for gvmsync.

Development helper.  Creates a localhost target, three
tasks and a set of ``project:*`` tags so that gvmsync has
something to synchronize:

    ClientA -> gvmsync-task-alpha + the default scanner
    ClientB -> gvmsync-task-beta
    (none)  -> gvmsync-task-untagged  (control: ignored)

The untagged task is a control: a correct gvmsync run must
never grant permissions on it.

Usage::

    gvm-script --gmp-username admin --gmp-password admin \\
        socket seed-test-data.gmp.py
"""

from __future__ import annotations

from argparse import Namespace

from gvm.protocols.gmp import Gmp

TARGET_NAME = "gvmsync-test-localhost"
TARGET_HOSTS = ["127.0.0.1"]
TARGET_PORT_RANGE = "1-1024"

TASKS: dict[str, str | None] = {
    "gvmsync-task-alpha": "ClientA",
    "gvmsync-task-beta": "ClientB",
    "gvmsync-task-untagged": None,
}


def _entity_type(name: str):
    """Resolve the EntityType enum across python-gvm versions."""
    try:
        from gvm.protocols.gmp.requests.v224 import EntityType
    except ImportError:
        from gvm.protocols.gmpv224 import EntityType
    return EntityType(name)


def _find_id(response, xpath: str, name: str) -> str | None:
    """Return the id of the first element matching name."""
    for elem in response.xpath(xpath):
        if elem.findtext("name", "") == name:
            return elem.get("id", "")
    return None


def _first_id(response, xpath: str) -> str | None:
    """Return the id of the first matching element."""
    elems = response.xpath(xpath)
    return elems[0].get("id", "") if elems else None


def _ensure_target(gmp: Gmp) -> str:
    """Create the test target if it does not exist."""
    existing = _find_id(gmp.get_targets(), ".//target", TARGET_NAME)
    if existing:
        print(f"  target '{TARGET_NAME}' already exists")
        return existing

    response = gmp.create_target(
        name=TARGET_NAME,
        hosts=TARGET_HOSTS,
        port_range=TARGET_PORT_RANGE,
        comment="Created by gvmsync seed script",
    )
    print(f"  created target '{TARGET_NAME}'")
    return response.get("id", "")


def _get_scan_config(gmp: Gmp) -> str | None:
    """Return the 'Full and fast' scan config id."""
    try:
        response = gmp.get_scan_configs()
    except AttributeError:
        response = gmp.get_configs()

    config_id = _find_id(response, ".//config", "Full and fast")
    if config_id:
        return config_id
    return _first_id(response, ".//config")


def _get_scanner(gmp: Gmp) -> str | None:
    """Return the default OpenVAS scanner id."""
    response = gmp.get_scanners()
    scanner_id = _find_id(response, ".//scanner", "OpenVAS Default")
    if scanner_id:
        return scanner_id
    return _first_id(response, ".//scanner")


def _ensure_task(
    gmp: Gmp,
    name: str,
    config_id: str,
    target_id: str,
    scanner_id: str,
) -> str:
    """Create a task if it does not exist."""
    existing = _find_id(gmp.get_tasks(), ".//task", name)
    if existing:
        print(f"  task '{name}' already exists")
        return existing

    response = gmp.create_task(
        name=name,
        config_id=config_id,
        target_id=target_id,
        scanner_id=scanner_id,
        comment="Created by gvmsync seed script",
    )
    print(f"  created task '{name}'")
    return response.get("id", "")


def _ensure_tag(
    gmp: Gmp,
    project: str,
    resource_type: str,
    resource_ids: list[str],
) -> None:
    """Attach a project:<name> tag to the given resources."""
    tag_name = f"project:{project}"
    existing = _find_id(gmp.get_tags(), ".//tag", tag_name)

    if existing:
        gmp.modify_tag(
            tag_id=existing,
            resource_type=_entity_type(resource_type),
            resource_ids=resource_ids,
        )
        print(f"  updated tag '{tag_name}' ({resource_type})")
        return

    gmp.create_tag(
        name=tag_name,
        resource_type=_entity_type(resource_type),
        resource_ids=resource_ids,
        comment="Created by gvmsync seed script",
    )
    print(f"  created tag '{tag_name}' ({resource_type})")


def main(gmp: Gmp, args: Namespace) -> None:
    """Seed the instance with gvmsync test data."""
    print("gvmsync seed - creating test data")

    print("\n--- Target ---")
    target_id = _ensure_target(gmp)

    config_id = _get_scan_config(gmp)
    scanner_id = _get_scanner(gmp)

    if not config_id or not scanner_id:
        print("  ERROR: no scan config or scanner available")
        return

    print("\n--- Tasks ---")
    task_ids: dict[str, str] = {}
    for task_name in TASKS:
        task_ids[task_name] = _ensure_task(
            gmp, task_name, config_id, target_id, scanner_id
        )

    print("\n--- Tags ---")
    by_project: dict[str, list[str]] = {}
    for task_name, project in TASKS.items():
        if project:
            by_project.setdefault(project, []).append(task_ids[task_name])

    for project, ids in by_project.items():
        _ensure_tag(gmp, project, "task", ids)

    # tag the scanner for ClientA so that scanner permissions
    # are exercised as well
    _ensure_tag(gmp, "ClientA", "scanner", [scanner_id])

    print("\n--- Done ---")
    print(f"Projects seeded: {', '.join(by_project)}")
    print("Untagged control task: gvmsync-task-untagged")


if __name__ == "__gmp__":
    main(gmp, args)  # type: ignore[name-defined]
