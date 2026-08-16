"""Tests for openamer_cli.system_info — OpenAmer self-system knowledge."""


def test_collect_returns_core_fields():
    from openamer_cli import system_info as si
    c = si.collect()
    assert set(c) >= {"os", "python", "arch", "ram_mb", "gpu", "locale",
                      "openamer", "tools_count", "skills_count"}
    assert c["os"]["system"] in ("Windows", "Linux", "Darwin")
    assert "python" in c["python"] or len(c["python"]) >= 3
    assert isinstance(c["tools_count"], int)
    assert "home" in c["openamer"]


def test_describe_is_human_readable():
    from openamer_cli import system_info as si
    d = si.describe()
    assert "OpenAmer runs on" in d
    assert "GPU" in d and "." in d
