"""Tests for openamer_cli.agent_ui — Visual Agent Builder Web UI."""
import json
import tempfile
import pathlib

import pytest

from openamer_cli.agent_ui import _AgentUIHandler, cmd_agent_ui, build_agent_ui_parser
from openamer_cli.agent_builder import AgentSpec, build_agent, list_agents, delete_agent


class TestAgentUI:
    def test_build_agent_ui_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        build_agent_ui_parser(sub)
        assert "agent-ui" in sub.choices

    def test_cmd_agent_ui_importable(self):
        assert callable(cmd_agent_ui)


class TestUIAPIResponses:
    """Test the HTTP handler logic without starting a server."""

    def test_handler_imports(self):
        from openamer_cli.agent_ui import _AgentUIHandler
        assert _AgentUIHandler is not None