# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._permissions."""

from __future__ import annotations

from gvmsync._permissions import (
    _get_group_permissions,
    _permission_exists,
    cleanup_orphaned_permissions,
    grant_permissions_for_project,
)
from gvmsync._resources import (
    ProjectResources,
    TaggedResource,
)


class TestNestedPermissions:
    """Nested <permissions> blocks must not be counted."""

    def test_effective_permissions_not_counted(
        self, mock_gmp, nested_permissions_xml
    ) -> None:
        mock_gmp.get_permissions.return_value = nested_permissions_xml

        records = _get_group_permissions(mock_gmp, "group-001")

        # three <permission> elements are present in the XML,
        # but only one is an actual result
        assert len(records) == 1
        assert records[0].permission_id == "perm-001"
        assert records[0].resource_id == "task-001"
        assert records[0].resource_type == "task"


class TestPermissionExists:
    """Tests for _permission_exists()."""

    def test_exists(self, mock_gmp, permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = permissions_xml
        result = _permission_exists(
            mock_gmp,
            "group-001",
            "task-001",
            "get_tasks",
        )
        assert result is True

    def test_not_exists(self, mock_gmp, empty_permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = empty_permissions_xml
        result = _permission_exists(
            mock_gmp,
            "group-001",
            "task-999",
            "get_tasks",
        )
        assert result is False

    def test_error_returns_false(self, mock_gmp) -> None:
        mock_gmp.get_permissions.side_effect = Exception("fail")
        result = _permission_exists(
            mock_gmp,
            "group-001",
            "task-001",
            "get_tasks",
        )
        assert result is False


class TestGrantPermissionsForProject:
    """Tests for grant_permissions_for_project()."""

    def test_grants_new_permissions(
        self, mock_gmp, empty_permissions_xml
    ) -> None:
        mock_gmp.get_permissions.return_value = empty_permissions_xml
        mock_gmp.create_permission.return_value = (
            "<create_permission_response status='201'/>"
        )

        resources = ProjectResources(
            project_name="Test",
            tasks=[
                TaggedResource(
                    resource_id="task-001",
                    name="Task 1",
                    resource_type="task",
                ),
            ],
        )

        count = grant_permissions_for_project(mock_gmp, "group-001", resources)
        assert count == 3

    def test_dry_run(self, mock_gmp, empty_permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = empty_permissions_xml

        resources = ProjectResources(
            project_name="Test",
            scanners=[
                TaggedResource(
                    resource_id="sc-001",
                    name="Scanner",
                    resource_type="scanner",
                ),
            ],
        )

        count = grant_permissions_for_project(
            mock_gmp,
            "group-001",
            resources,
            dry_run=True,
        )
        assert count == 1
        mock_gmp.create_permission.assert_not_called()

    def test_no_resources(self, mock_gmp) -> None:
        resources = ProjectResources(project_name="Empty")
        count = grant_permissions_for_project(mock_gmp, "group-001", resources)
        assert count == 0


class TestGetGroupPermissions:
    """Tests for _get_group_permissions()."""

    def test_parses_permissions(self, mock_gmp, permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = permissions_xml
        result = _get_group_permissions(mock_gmp, "group-001")
        assert len(result) == 2
        assert result[0].permission_name == "get_tasks"
        assert result[0].resource_id == "task-001"

    def test_empty_response(self, mock_gmp, empty_permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = empty_permissions_xml
        result = _get_group_permissions(mock_gmp, "group-001")
        assert result == []


class TestCleanupOrphanedPermissions:
    """Tests for cleanup_orphaned_permissions()."""

    def test_nothing_to_clean(self, mock_gmp, empty_permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = empty_permissions_xml

        stats = cleanup_orphaned_permissions(
            mock_gmp,
            {"TestProject": "group-001"},
        )
        assert stats.scanned == 0
        assert stats.removed == 0

    def test_dry_run_cleanup(self, mock_gmp, permissions_xml) -> None:
        mock_gmp.get_permissions.return_value = permissions_xml
        mock_gmp.get_tasks.return_value = "<get_tasks_response/>"
        mock_gmp.get_scanners.return_value = "<get_scanners_response/>"

        stats = cleanup_orphaned_permissions(
            mock_gmp,
            {"TestProject": "group-001"},
            dry_run=True,
        )
        assert stats.scanned == 2
        assert stats.removed == 2
        mock_gmp.delete_permission.assert_not_called()
