# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._groups."""

from __future__ import annotations

from gvmsync._groups import (
    ensure_group,
    get_existing_groups,
)


class TestGetExistingGroups:
    """Tests for get_existing_groups()."""

    def test_parses_groups(self, mock_gmp, groups_xml) -> None:
        mock_gmp.get_groups.return_value = groups_xml

        result = get_existing_groups(mock_gmp)

        assert result == {
            "TestProject": "group-001",
            "OtherGroup": "group-002",
        }

    def test_empty_groups(self, mock_gmp) -> None:
        mock_gmp.get_groups.return_value = "<get_groups_response/>"
        result = get_existing_groups(mock_gmp)
        assert result == {}


class TestEnsureGroup:
    """Tests for ensure_group()."""

    def test_group_exists(self, mock_gmp) -> None:
        existing = {"MyProject": "group-123"}
        result = ensure_group(
            mock_gmp,
            "MyProject",
            existing,
        )
        assert result == "group-123"
        mock_gmp.create_group.assert_not_called()

    def test_dry_run_new_group(self, mock_gmp) -> None:
        existing: dict[str, str] = {}
        result = ensure_group(
            mock_gmp,
            "NewProject",
            existing,
            dry_run=True,
        )
        assert result == "dry-run-NewProject"
        mock_gmp.create_group.assert_not_called()

    def test_creates_new_group(
        self,
        mock_gmp,
        create_group_response_xml,
    ) -> None:
        mock_gmp.create_group.return_value = create_group_response_xml
        existing: dict[str, str] = {}

        result = ensure_group(
            mock_gmp,
            "NewProject",
            existing,
        )

        assert result == "group-new-001"
        assert "NewProject" in existing
        mock_gmp.create_group.assert_called_once()
