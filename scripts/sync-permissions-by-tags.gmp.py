# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Synchronize GVM permissions based on project tags.

This script automates multi-tenant permission management
in Greenbone Community Edition.  Resources (tasks, scanners,
reports) are tagged with ``project:<name>`` in the web UI.
The script discovers those tags, ensures a GVM group exists
for each project, and grants the minimum required permissions
to each group.  An optional cleanup phase revokes orphaned
permissions when tags are removed or resources are deleted.

Usage with gvm-script::

    gvm-script --gmp-username admin --gmp-password secret \\
        ssh --hostname <gvm-host> \\
        sync-permissions-by-tags.gmp.py

    # dry-run mode
    gvm-script ... sync-permissions-by-tags.gmp.py \\
        --dry-run

    # with cleanup
    gvm-script ... sync-permissions-by-tags.gmp.py \\
        --cleanup

    # inventory only
    gvm-script ... sync-permissions-by-tags.gmp.py \\
        --all
"""

from __future__ import annotations

import time
from argparse import Namespace
from datetime import UTC, datetime

from gvm.protocols.gmp import Gmp

RESOURCE_TYPES = ("scanner", "task", "report")

PERMISSION_CONFIG: dict[str, list[str]] = {
    "scanner": ["get_scanners"],
    "task": ["get_tasks", "start_task", "stop_task"],
    "report": ["get_reports"],
}


# ------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------


def _extract_project_names(element) -> list[str]:
    """Extract project names from project:* tags."""
    projects: list[str] = []
    for tag in element.xpath(".//tag"):
        tag_name = tag.findtext("name", "")
        if tag_name.startswith("project:"):
            project = tag_name.split("project:", 1)[1]
            if project and project not in projects:
                projects.append(project)
    return projects


def _extract_all_tags(element) -> list[str]:
    """Extract all tag names."""
    tags: list[str] = []
    for tag in element.xpath(".//tag"):
        tag_name = tag.findtext("name", "")
        if tag_name and tag_name not in tags:
            tags.append(tag_name)
    return tags


def _get_owner(element) -> str:
    """Extract resource owner name."""
    owner = element.find(".//owner")
    if owner is not None:
        name = owner.findtext("name", "")
        if name:
            return name
    return "Unknown"


def _get_func(gmp: Gmp, res_type: str):
    """Return the appropriate get function."""
    return {
        "scanner": gmp.get_scanners,
        "task": gmp.get_tasks,
        "report": gmp.get_reports,
    }.get(res_type)


# ------------------------------------------------------------------
# inventory (--all)
# ------------------------------------------------------------------


def _list_all_resources(gmp: Gmp) -> None:
    """Print a complete inventory of all resources."""
    print("\n--- Inventory: all resources ---")

    total = tagged = project_tagged = 0

    for res_type in RESOURCE_TYPES:
        func = _get_func(gmp, res_type)
        if func is None:
            continue

        print(f"\n== {res_type.upper()}S ==")

        try:
            response = func(details=True)
            elements = response.xpath(f".//{res_type}")

            if not elements:
                print(f"  No {res_type}s found")
                continue

            print(f"  Found {len(elements)} {res_type}(s)")

            for elem in elements:
                total += 1
                rid = elem.get("id", "")
                name = elem.findtext("name", "unknown")
                owner = _get_owner(elem)
                all_tags = _extract_all_tags(elem)
                ptags = _extract_project_names(elem)
                short = name[:50] + "..." if len(name) > 50 else name

                if ptags:
                    tagged += 1
                    project_tagged += 1
                    tag_str = ", ".join(all_tags)
                    print(
                        f"  [SYNC] {short}  "
                        f"id={rid}  owner={owner}  "
                        f"tags={tag_str}"
                    )
                elif all_tags:
                    tagged += 1
                    tag_str = ", ".join(all_tags)
                    print(
                        f"  [----] {short}  "
                        f"id={rid}  owner={owner}  "
                        f"tags={tag_str}  "
                        f"(no project:* tag)"
                    )
                else:
                    print(
                        f"  [----] {short}  id={rid}  owner={owner}  (no tags)"
                    )

        except Exception as exc:
            print(f"  ERROR: failed to retrieve {res_type}s: {exc}")

    print("\n--- Summary ---")
    print(f"Total: {total}")
    print(f"With tags: {tagged}")
    print(f"With project:* (will sync): {project_tagged}")
    print(f"Without tags: {total - tagged}")


# ------------------------------------------------------------------
# phase 1: resource extraction
# ------------------------------------------------------------------


def _collect_resources(
    gmp: Gmp,
) -> dict[str, dict[str, list[dict[str, str]]]]:
    """Collect resources with project:* tags."""
    print("\n--- Phase 1: Resource extraction ---")

    projects: dict[str, dict[str, list[dict[str, str]]]] = {}

    for res_type in RESOURCE_TYPES:
        func = _get_func(gmp, res_type)
        if func is None:
            continue

        print(f"  Extracting {res_type}s with project:* tags...")

        try:
            response = func(details=True)
            elements = response.xpath(f".//{res_type}")
            count = 0

            for elem in elements:
                pnames = _extract_project_names(elem)
                if not pnames:
                    continue
                count += 1
                rid = elem.get("id", "")
                rname = elem.findtext("name", "unknown")
                res = {
                    "id": rid,
                    "name": rname,
                    "type": res_type,
                }

                for pname in pnames:
                    if pname not in projects:
                        projects[pname] = {t: [] for t in RESOURCE_TYPES}
                    existing_ids = [r["id"] for r in projects[pname][res_type]]
                    if rid not in existing_ids:
                        projects[pname][res_type].append(res)

            print(f"    {count}/{len(elements)} {res_type}(s) tagged")
        except Exception as exc:
            print(f"    ERROR: {res_type}s: {exc}")

    if not projects:
        print("  No resources with project:* tags found")
    else:
        print(f"  Discovered {len(projects)} project(s)")

    return projects


# ------------------------------------------------------------------
# phase 2: groups
# ------------------------------------------------------------------


def _get_groups(gmp: Gmp) -> dict[str, str]:
    """Get existing groups."""
    print("\n--- Phase 2: Group verification ---")
    response = gmp.get_groups()
    groups: dict[str, str] = {}
    for g in response.xpath(".//group"):
        name = g.findtext("name", "")
        gid = g.get("id", "")
        if name and gid:
            groups[name] = gid
    print(f"  Loaded {len(groups)} existing group(s)")
    return groups


def _ensure_group(
    gmp: Gmp,
    name: str,
    groups: dict[str, str],
    *,
    dry_run: bool = False,
) -> str | None:
    """Ensure group exists."""
    if name in groups:
        return groups[name]

    if dry_run:
        print(f"  [dry-run] Would create group '{name}'")
        return f"dry-run-{name}"

    try:
        now = datetime.now(tz=UTC).isoformat()
        response = gmp.create_group(
            name=name,
            comment=f"Auto-created by gvmsync - {now}",
        )
        gid = response.get("id", "")
        groups[name] = gid
        print(f"  Created group '{name}'")
        return gid
    except Exception as exc:
        print(f"  ERROR creating group '{name}': {exc}")
        return None


# ------------------------------------------------------------------
# phase 3: permissions
# ------------------------------------------------------------------


def _permission_exists(
    gmp: Gmp,
    group_id: str,
    resource_id: str,
    perm_name: str,
) -> bool:
    """Check if permission already exists."""
    try:
        response = gmp.get_permissions(
            filter_string=(
                f"subject_uuid={group_id} and "
                f"resource_uuid={resource_id} and "
                f'name="{perm_name}"'
            ),
        )
        return len(response.xpath(".//permission")) > 0
    except Exception:
        return False


def _grant_permissions(
    gmp: Gmp,
    group_id: str,
    resources: dict[str, list[dict[str, str]]],
    *,
    dry_run: bool = False,
) -> int:
    """Grant permissions for a project's resources."""
    total = 0

    for res_type, perms in PERMISSION_CONFIG.items():
        res_list = resources.get(res_type, [])
        if not res_list:
            continue

        for res in res_list:
            for perm in perms:
                if _permission_exists(
                    gmp,
                    group_id,
                    res["id"],
                    perm,
                ):
                    continue

                if dry_run:
                    print(
                        f"    [dry-run] Would grant '{perm}' on '{res['name']}'"
                    )
                    total += 1
                    continue

                try:
                    now = datetime.now(tz=UTC).isoformat()
                    gmp.create_permission(
                        name=perm,
                        subject_id=group_id,
                        subject_type="group",
                        resource_id=res["id"],
                        resource_type=res["type"],
                        comment=f"gvmsync - {now}",
                    )
                    total += 1
                    print(f"    Granted '{perm}' on '{res['name']}'")
                except Exception as exc:
                    print(f"    ERROR: '{perm}' on '{res['name']}': {exc}")

    return total


# ------------------------------------------------------------------
# phase 4: cleanup
# ------------------------------------------------------------------


def _cleanup(
    gmp: Gmp,
    groups: dict[str, str],
    *,
    dry_run: bool = False,
) -> None:
    """Remove orphaned permissions."""
    print("\n--- Phase 4: Garbage collection ---")

    scanned = removed = 0

    for group_name, group_id in groups.items():
        print(f"  Checking group '{group_name}'...")

        try:
            response = gmp.get_permissions(
                filter_string=(f"subject_uuid={group_id}"),
            )
        except Exception:
            continue

        perms = response.xpath(".//permission")
        if not perms:
            continue

        scanned += len(perms)

        for perm in perms:
            res_elem = perm.find(".//resource")
            if res_elem is None:
                continue

            res_type_elem = res_elem.find("type")
            res_type = res_type_elem.text if res_type_elem is not None else ""
            res_id = res_elem.get("id", "")
            res_name = res_elem.findtext("name", "unknown")
            perm_id = perm.get("id", "")
            perm_name = perm.findtext("name", "")

            func = _get_func(gmp, res_type)
            if func is None:
                continue

            still_tagged = False
            try:
                resp = func(
                    filter_string=f"uuid={res_id}",
                    details=True,
                )
                xpath = f".//{res_type}[@id='{res_id}']"
                elem = resp.find(xpath)
                if elem is not None:
                    prjs = _extract_project_names(elem)
                    still_tagged = group_name in prjs
            except Exception:
                still_tagged = True

            if still_tagged:
                continue

            if dry_run:
                print(
                    f"    [dry-run] Would remove "
                    f"'{perm_name}' from '{res_name}'"
                )
                removed += 1
            else:
                try:
                    gmp.delete_permission(permission_id=perm_id)
                    removed += 1
                    print(f"    Removed '{perm_name}' from '{res_name}'")
                except Exception as exc:
                    print(f"    ERROR removing '{perm_name}': {exc}")

    print(f"  Cleanup: scanned={scanned}, removed={removed}")


# ------------------------------------------------------------------
# main
# ------------------------------------------------------------------


def _parse_script_args(
    args: Namespace,
) -> tuple[bool, bool, bool]:
    """Parse script-specific arguments.

    Returns:
        Tuple of (dry_run, cleanup, show_all).
    """
    script_args = args.script[1:]
    dry_run = "--dry-run" in script_args
    cleanup = "--cleanup" in script_args
    show_all = "--all" in script_args
    return dry_run, cleanup, show_all


def main(gmp: Gmp, args: Namespace) -> None:
    """Entry point for gvm-script execution.

    Args:
        gmp: An authenticated GMP connection provided
            by gvm-script.
        args: Arguments namespace from gvm-script.
    """
    dry_run, cleanup, show_all = _parse_script_args(args)

    print("gvmsync - Permission Sync by Tags")
    print("  Version: 1.0.0")

    if show_all:
        _list_all_resources(gmp)
        return

    mode = "DRY-RUN" if dry_run else "SYNC"
    print(f"  Mode: {mode}")
    print(f"  Cleanup: {'ON' if cleanup else 'OFF'}")

    start = time.time()

    projects = _collect_resources(gmp)
    groups = _get_groups(gmp)

    total_perms = 0

    if projects:
        print("\n--- Phase 3: Permission configuration ---")
        for pname, resources in projects.items():
            print(f"\n  Project: {pname}")
            gid = _ensure_group(gmp, pname, groups, dry_run=dry_run)
            if not gid:
                continue
            total_perms += _grant_permissions(
                gmp, gid, resources, dry_run=dry_run
            )

    if cleanup:
        _cleanup(gmp, groups, dry_run=dry_run)

    elapsed = time.time() - start
    print("\n--- Summary ---")
    print(
        f"Projects: {len(projects)} | "
        f"Permissions: {total_perms} | "
        f"Time: {elapsed:.2f}s"
    )
    print("Done.")


if __name__ == "__gmp__":
    main(gmp, args)  # type: ignore[name-defined]
