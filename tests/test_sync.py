# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._sync."""

from __future__ import annotations

from gvmsync._sync import run_sync


class TestRunSync:
    """Tests for run_sync()."""

    def test_full_sync(
        self,
        mock_gmp,
        task_with_tag_xml,
        scanner_with_tag_xml,
        report_no_tag_xml,
        groups_xml,
        empty_permissions_xml,
    ) -> None:
        mock_gmp.get_tasks.return_value = task_with_tag_xml
        mock_gmp.get_scanners.return_value = scanner_with_tag_xml
        mock_gmp.get_reports.return_value = report_no_tag_xml
        mock_gmp.get_groups.return_value = groups_xml
        mock_gmp.get_permissions.return_value = empty_permissions_xml
        mock_gmp.create_permission.return_value = (
            "<create_permission_response status='201'/>"
        )

        result = run_sync(mock_gmp)

        assert result.projects_found == 1
        assert result.permissions_created > 0
        assert result.cleanup is None
        assert result.elapsed_seconds >= 0

    def test_no_projects(self, mock_gmp, report_no_tag_xml) -> None:
        mock_gmp.get_tasks.return_value = "<get_tasks_response/>"
        mock_gmp.get_scanners.return_value = "<get_scanners_response/>"
        mock_gmp.get_reports.return_value = "<get_reports_response/>"
        mock_gmp.get_groups.return_value = "<get_groups_response/>"

        result = run_sync(mock_gmp)

        assert result.projects_found == 0
        assert result.permissions_created == 0

    def test_dry_run(
        self,
        mock_gmp,
        task_with_tag_xml,
        scanner_with_tag_xml,
        report_no_tag_xml,
        groups_xml,
        empty_permissions_xml,
    ) -> None:
        mock_gmp.get_tasks.return_value = task_with_tag_xml
        mock_gmp.get_scanners.return_value = scanner_with_tag_xml
        mock_gmp.get_reports.return_value = report_no_tag_xml
        mock_gmp.get_groups.return_value = groups_xml
        mock_gmp.get_permissions.return_value = empty_permissions_xml

        result = run_sync(mock_gmp, dry_run=True)

        assert result.projects_found == 1
        assert result.permissions_created > 0
        mock_gmp.create_permission.assert_not_called()

    def test_with_cleanup(
        self,
        mock_gmp,
        task_with_tag_xml,
        scanner_with_tag_xml,
        report_no_tag_xml,
        groups_xml,
        empty_permissions_xml,
    ) -> None:
        mock_gmp.get_tasks.return_value = task_with_tag_xml
        mock_gmp.get_scanners.return_value = scanner_with_tag_xml
        mock_gmp.get_reports.return_value = report_no_tag_xml
        mock_gmp.get_groups.return_value = groups_xml
        mock_gmp.get_permissions.return_value = empty_permissions_xml
        mock_gmp.create_permission.return_value = (
            "<create_permission_response status='201'/>"
        )

        result = run_sync(mock_gmp, enable_cleanup=True)

        assert result.cleanup is not None
