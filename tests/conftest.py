# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Shared test fixtures for gvmsync."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from lxml import etree


@pytest.fixture
def mock_gmp() -> MagicMock:
    """Return a mock GMP connection."""
    return MagicMock()


@pytest.fixture
def task_with_tag_xml() -> str:
    """Task XML with a project:TestProject tag."""
    return """
    <get_tasks_response status="200">
      <task id="task-001">
        <name>Scan Client A</name>
        <owner><name>admin</name></owner>
        <tag>
          <name>project:TestProject</name>
        </tag>
      </task>
      <task id="task-002">
        <name>Scan Client B</name>
        <owner><name>admin</name></owner>
      </task>
    </get_tasks_response>
    """


@pytest.fixture
def scanner_with_tag_xml() -> str:
    """Scanner XML with a project:TestProject tag."""
    return """
    <get_scanners_response status="200">
      <scanner id="scanner-001">
        <name>OpenVAS Default</name>
        <owner><name>admin</name></owner>
        <tag>
          <name>project:TestProject</name>
        </tag>
      </scanner>
    </get_scanners_response>
    """


@pytest.fixture
def report_no_tag_xml() -> str:
    """Report XML without project tags."""
    return """
    <get_reports_response status="200">
      <report id="report-001">
        <name>Report 1</name>
        <owner><name>admin</name></owner>
      </report>
    </get_reports_response>
    """


@pytest.fixture
def groups_xml() -> str:
    """Groups listing XML."""
    return """
    <get_groups_response status="200">
      <group id="group-001">
        <name>TestProject</name>
      </group>
      <group id="group-002">
        <name>OtherGroup</name>
      </group>
    </get_groups_response>
    """


@pytest.fixture
def permissions_xml() -> str:
    """Permissions listing XML with resource details."""
    return """
    <get_permissions_response status="200">
      <permission id="perm-001">
        <name>get_tasks</name>
        <resource id="task-001">
          <name>Scan Client A</name>
          <type>task</type>
        </resource>
      </permission>
      <permission id="perm-002">
        <name>get_scanners</name>
        <resource id="scanner-001">
          <name>OpenVAS Default</name>
          <type>scanner</type>
        </resource>
      </permission>
    </get_permissions_response>
    """


@pytest.fixture
def empty_permissions_xml() -> str:
    """Empty permissions response."""
    return """
    <get_permissions_response status="200">
    </get_permissions_response>
    """


@pytest.fixture
def create_group_response_xml() -> str:
    """Successful create_group response."""
    return """
    <create_group_response status="201"
      id="group-new-001">
    </create_group_response>
    """


@pytest.fixture
def task_element() -> etree._Element:
    """A single task element with a project tag."""
    xml_str = """
    <task id="task-001">
      <name>Scan Client A</name>
      <owner><name>admin</name></owner>
      <tag><name>project:Alpha</name></tag>
      <tag><name>project:Beta</name></tag>
      <tag><name>priority:high</name></tag>
    </task>
    """
    return etree.fromstring(xml_str)


@pytest.fixture
def task_element_no_tags() -> etree._Element:
    """A task element without any tags."""
    xml_str = """
    <task id="task-002">
      <name>Untagged Task</name>
      <owner><name>user1</name></owner>
    </task>
    """
    return etree.fromstring(xml_str)


@pytest.fixture
def task_element_no_owner() -> etree._Element:
    """A task element without an owner."""
    xml_str = """
    <task id="task-003">
      <name>Orphan Task</name>
      <tag><name>project:Gamma</name></tag>
    </task>
    """
    return etree.fromstring(xml_str)
