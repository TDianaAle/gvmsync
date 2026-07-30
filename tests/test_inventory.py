# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._inventory."""

from __future__ import annotations

from gvmsync._inventory import list_all_resources


class TestListAllResources:
    """Tests for list_all_resources()."""

    def test_lists_resources(
        self,
        mock_gmp,
        task_with_tag_xml,
        scanner_with_tag_xml,
        report_no_tag_xml,
    ) -> None:
        mock_gmp.get_scanners.return_value = scanner_with_tag_xml
        mock_gmp.get_tasks.return_value = task_with_tag_xml
        mock_gmp.get_reports.return_value = report_no_tag_xml

        list_all_resources(mock_gmp)

        mock_gmp.get_scanners.assert_called_once()
        mock_gmp.get_tasks.assert_called_once()
        mock_gmp.get_reports.assert_called_once()

    def test_handles_empty(self, mock_gmp) -> None:
        mock_gmp.get_scanners.return_value = "<get_scanners_response/>"
        mock_gmp.get_tasks.return_value = "<get_tasks_response/>"
        mock_gmp.get_reports.return_value = "<get_reports_response/>"

        list_all_resources(mock_gmp)
