# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._resources."""

from __future__ import annotations

from lxml import etree

from gvmsync._resources import (
    collect_tagged_resources,
    extract_all_tags,
    extract_project_names,
    get_owner,
)
from gvmsync._xml import select_resources


class TestExtractProjectNames:
    """Tests for extract_project_names()."""

    def test_single_project(self, task_element: etree._Element) -> None:
        result = extract_project_names(task_element)
        assert "Alpha" in result
        assert "Beta" in result

    def test_no_project_tags(
        self, task_element_no_tags: etree._Element
    ) -> None:
        result = extract_project_names(task_element_no_tags)
        assert result == []

    def test_empty_element(self) -> None:
        elem = etree.fromstring("<task/>")
        result = extract_project_names(elem)
        assert result == []

    def test_no_duplicates(self) -> None:
        xml_str = """
        <task>
          <tag><name>project:Same</name></tag>
          <tag><name>project:Same</name></tag>
        </task>
        """
        elem = etree.fromstring(xml_str)
        result = extract_project_names(elem)
        assert result == ["Same"]


class TestExtractAllTags:
    """Tests for extract_all_tags()."""

    def test_with_tags(self, task_element: etree._Element) -> None:
        result = extract_all_tags(task_element)
        assert "project:Alpha" in result
        assert "project:Beta" in result
        assert "priority:high" in result
        assert len(result) == 3

    def test_no_tags(self, task_element_no_tags: etree._Element) -> None:
        result = extract_all_tags(task_element_no_tags)
        assert result == []


class TestGetOwner:
    """Tests for get_owner()."""

    def test_with_owner(self, task_element: etree._Element) -> None:
        assert get_owner(task_element) == "admin"

    def test_without_owner(self, task_element_no_owner: etree._Element) -> None:
        assert get_owner(task_element_no_owner) == "Unknown"


class TestSelectResources:
    """Tests for the nested-element handling of GMP responses."""

    def test_nested_report_counted_once(self, nested_report_xml: str) -> None:
        root = etree.fromstring(nested_report_xml.encode())
        assert len(root.xpath(".//report")) == 2
        assert len(select_resources(root, "report")) == 1

    def test_nested_scanner_engine_ignored(
        self, nested_scanner_xml: str
    ) -> None:
        root = etree.fromstring(nested_scanner_xml.encode())
        assert len(root.xpath(".//scanner")) == 2
        selected = select_resources(root, "scanner")
        assert len(selected) == 1
        assert selected[0].get("id") == "scanner-001"


class TestCollectTaggedResources:
    """Tests for collect_tagged_resources()."""

    def test_nested_report_yields_one_resource(
        self,
        mock_gmp,
        nested_report_xml,
        nested_scanner_xml,
    ) -> None:
        mock_gmp.get_tasks.return_value = "<get_tasks_response/>"
        mock_gmp.get_scanners.return_value = nested_scanner_xml
        mock_gmp.get_reports.return_value = nested_report_xml

        result = collect_tagged_resources(mock_gmp)

        project = result["TestProject"]
        assert len(project.reports) == 1
        assert project.reports[0].resource_id == "report-001"
        assert len(project.scanners) == 1
        assert project.scanners[0].resource_id == "scanner-001"

    def test_collects_tagged(
        self,
        mock_gmp,
        task_with_tag_xml,
        scanner_with_tag_xml,
        report_no_tag_xml,
    ) -> None:
        mock_gmp.get_tasks.return_value = task_with_tag_xml
        mock_gmp.get_scanners.return_value = scanner_with_tag_xml
        mock_gmp.get_reports.return_value = report_no_tag_xml

        result = collect_tagged_resources(mock_gmp)

        assert "TestProject" in result
        project = result["TestProject"]
        assert len(project.tasks) == 1
        assert project.tasks[0].name == "Scan Client A"
        assert len(project.scanners) == 1
        assert len(project.reports) == 0

    def test_no_tagged_resources(self, mock_gmp, report_no_tag_xml) -> None:
        mock_gmp.get_tasks.return_value = report_no_tag_xml.replace(
            "report", "task"
        ).replace("get_reports", "get_tasks")
        mock_gmp.get_scanners.return_value = "<get_scanners_response/>"
        mock_gmp.get_reports.return_value = report_no_tag_xml

        result = collect_tagged_resources(mock_gmp)
        assert result == {}
