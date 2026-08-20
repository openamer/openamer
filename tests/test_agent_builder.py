"""Tests for openamer_cli.agent_builder — visual agent builder."""
import json
import pathlib
import tempfile

import pytest

from openamer_cli.agent_builder import (
    AgentSpec,
    build_agent,
    list_agents,
    delete_agent,
    show_agent,
    create_agent_from_description,
)


@pytest.fixture(autouse=True)
def isolate_home(monkeypatch):
    """Redirect agent storage to a temp dir."""
    with tempfile.TemporaryDirectory() as tmp:
        p = pathlib.Path(tmp)
        agents_dir = p / "agents"
        skills_dir = p / "skills"
        agents_dir.mkdir(parents=True)
        skills_dir.mkdir(parents=True)
        monkeypatch.setattr("openamer_cli.agent_builder.AGENTS_DIR", agents_dir)
        monkeypatch.setattr("openamer_cli.agent_builder.SKILLS_BASE", skills_dir)
        monkeypatch.setattr("openamer_cli.agent_builder._OPENAMER_HOME", p)
        yield p


class TestAgentSpec:
    def test_default_creation(self):
        spec = AgentSpec(
            name="test-agent",
            description="A test agent",
            goal="Monitor system health",
        )
        assert spec.name == "test-agent"
        assert spec.goal == "Monitor system health"
        assert spec.skills == []
        assert spec.cron_schedule is None

    def test_to_dict(self):
        spec = AgentSpec(
            name="dict-test",
            description="Test",
            goal="Goal",
            skills=["web-research"],
        )
        d = spec.to_dict()
        assert d["name"] == "dict-test"
        assert d["skills"] == ["web-research"]


class TestBuildAgent:
    def test_build_basic_agent(self, isolate_home):
        spec = AgentSpec(
            name="my-agent",
            description="My first agent",
            goal="Send daily summary",
        )
        result = build_agent(spec)
        assert result["name"] == "my-agent"

        agent_file = isolate_home / "agents" / "my-agent.json"
        assert agent_file.exists()

        skill_file = isolate_home / "skills" / "my-agent" / "SKILL.md"
        assert skill_file.exists()
        content = skill_file.read_text(encoding="utf-8")
        assert "Send daily summary" in content

    def test_build_with_skills(self, isolate_home):
        spec = AgentSpec(
            name="skill-agent",
            description="Agent with skills",
            goal="Use multiple skills",
            skills=["web-research", "github"],
        )
        result = build_agent(spec)
        assert result["name"] == "skill-agent"
        assert result["skills"] == ["web-research", "github"]

    def test_build_creates_skill_dir(self, isolate_home):
        build_agent(AgentSpec(name="dir-test", description="D", goal="G"))
        skill_dir = isolate_home / "skills" / "dir-test"
        assert skill_dir.exists()
        assert (skill_dir / "SKILL.md").exists()

    def test_build_creates_agent_json(self, isolate_home):
        build_agent(AgentSpec(name="json-test", description="J", goal="G"))
        agent_file = isolate_home / "agents" / "json-test.json"
        assert agent_file.exists()
        data = json.loads(agent_file.read_text(encoding="utf-8"))
        assert data["name"] == "json-test"


class TestListAgents:
    def test_list_empty(self, isolate_home):
        agents = list_agents()
        assert agents == []

    def test_list_with_agents(self, isolate_home):
        build_agent(AgentSpec(name="agent-a", description="A", goal="Goal A"))
        build_agent(AgentSpec(name="agent-b", description="B", goal="Goal B"))
        agents = list_agents()
        assert len(agents) == 2
        names = [a["name"] for a in agents]
        assert "agent-a" in names
        assert "agent-b" in names


class TestShowAgent:
    def test_show_existing(self, isolate_home):
        build_agent(AgentSpec(name="show-me", description="Show test", goal="Show goal"))
        result = show_agent("show-me")
        assert result is not None
        assert result["name"] == "show-me"
        assert result["description"] == "Show test"

    def test_show_missing(self, isolate_home):
        result = show_agent("does-not-exist")
        assert result is None


class TestDeleteAgent:
    def test_delete_existing(self, isolate_home):
        build_agent(AgentSpec(name="delete-me", description="To delete", goal="Bye"))
        assert delete_agent("delete-me") is True
        assert list_agents() == []

    def test_delete_missing(self, isolate_home):
        assert delete_agent("ghost") is False

    def test_delete_removes_skill_dir(self, isolate_home):
        build_agent(AgentSpec(name="del-skill", description="D", goal="G"))
        skill_dir = isolate_home / "skills" / "del-skill"
        assert skill_dir.exists()
        delete_agent("del-skill")
        assert not skill_dir.exists()


class TestCreateFromDescription:
    def test_basic_description(self, isolate_home):
        spec = create_agent_from_description("Send daily report every 24 hours")
        assert isinstance(spec, AgentSpec)
        assert spec.goal is not None

    def test_schedule_detection(self, isolate_home):
        spec = create_agent_from_description("Check server every 30 minutes")
        assert spec.cron_schedule is not None

    def test_skills_detection(self, isolate_home):
        spec = create_agent_from_description("Research topics using skills web-research,github")
        assert len(spec.skills) > 0

    def test_minimal_description(self, isolate_home):
        spec = create_agent_from_description("Hi")
        assert isinstance(spec, AgentSpec)

    def test_name_from_description(self, isolate_home):
        spec = create_agent_from_description("Monitor server health every hour")
        # Should generate a name from the description
        assert spec.name is not None


class TestCLI:
    def test_build_agent_parser(self):
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers()
        from openamer_cli.subcommands.agent import build_agent_parser
        build_agent_parser(sub)
        assert "agent" in sub.choices

    def test_all_cmds_importable(self):
        from openamer_cli.agent_builder import (
            build_agent, list_agents, delete_agent, show_agent,
            create_agent_from_description,
        )
        assert callable(build_agent)
        assert callable(list_agents)
        assert callable(delete_agent)
        assert callable(show_agent)
        assert callable(create_agent_from_description)