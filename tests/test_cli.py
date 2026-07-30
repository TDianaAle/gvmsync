# SPDX-FileCopyrightText: 2025-2026 Diana Tichy
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Tests for gvmsync._cli."""

from __future__ import annotations

import os
from unittest.mock import patch

from gvmsync._cli import _build_parser


class TestBuildParser:
    """Tests for _build_parser()."""

    def test_defaults(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["--admin", "admin", "--admin-pass", "pw"])
        assert args.admin == "admin"
        assert args.admin_pass == "pw"
        assert args.socket == "/run/gvmd/gvmd.sock"
        assert args.timeout == 60
        assert args.dry_run is False
        assert args.enable_cleanup is False
        assert args.all is False
        assert args.verbose is False

    def test_all_flags(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(
            [
                "--admin",
                "admin",
                "--admin-pass",
                "pw",
                "--dry-run",
                "--enable-cleanup",
                "--all",
                "--verbose",
                "--socket",
                "/tmp/gvmd.sock",
                "--timeout",
                "120",
            ]
        )
        assert args.dry_run is True
        assert args.enable_cleanup is True
        assert args.all is True
        assert args.verbose is True
        assert args.socket == "/tmp/gvmd.sock"
        assert args.timeout == 120


class TestCredentials:
    """Test credential resolution."""

    def test_env_vars(self) -> None:
        with patch.dict(
            os.environ,
            {
                "GVM_ADMIN_USER": "envuser",
                "GVM_ADMIN_PASS": "envpass",
            },
        ):
            user = os.environ.get("GVM_ADMIN_USER")
            passwd = os.environ.get("GVM_ADMIN_PASS")
            assert user == "envuser"
            assert passwd == "envpass"

    def test_cli_overrides_env(self) -> None:
        parser = _build_parser()
        args = parser.parse_args(["--admin", "clipass", "--admin-pass", "pw"])
        with patch.dict(
            os.environ,
            {"GVM_ADMIN_USER": "envuser"},
        ):
            admin = args.admin or os.environ.get("GVM_ADMIN_USER")
            assert admin == "clipass"
