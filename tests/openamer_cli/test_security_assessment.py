"""Real HTTP proof/control contracts for native local security assessment."""
import argparse
import json

import pytest

from openamer_cli import security_assessment as sa


@pytest.mark.parametrize('origin', ['https://example.com', 'http://localhost:80', 'http://127.0.0.1:80/path', 'http://user@127.0.0.1:80', 'http://127.0.0.1:80?x=1'])
def test_scope_rejects_nonliteral_or_ambiguous_origins(origin):
    with pytest.raises(ValueError):
        sa.validate_manifest({'origin': origin, 'checks': []})


def test_authorization_required_before_network(tmp_path):
    with pytest.raises(ValueError, match='authorization'):
        sa.assess({'origin': 'http://127.0.0.1:9', 'checks': []}, authorized=False)


def test_local_lab_proves_vulnerable_and_fixed(tmp_path):
    result = sa.run_lab(tmp_path)
    assert result['verified'] is True
    assert result['vulnerable']['confirmed'] == 2
    assert result['fixed']['confirmed'] == 0
    assert all(c['status'] == 'not_reproduced' for c in result['fixed']['checks'])
    for check in result['vulnerable']['checks']:
        assert check['status'] == 'confirmed'
        assert len(check['exchanges']) == 3
        assert all(e['request'] and e['response'] for e in check['exchanges'])
    assert json.loads((tmp_path / 'lab.json').read_text())['verified']


def test_probe_commands_preserve_legacy_dispatch():
    from openamer_cli.subcommands.security import build_security_parser
    parser = argparse.ArgumentParser()
    legacy = lambda args: 42
    build_security_parser(parser.add_subparsers(), cmd_security=legacy)
    assert parser.parse_args(['security', 'posture']).func is legacy
    args = parser.parse_args(['security', 'assess', 'manifest.json', '--authorized', '--output', 'report.json'])
    assert args.func is not legacy


@pytest.mark.parametrize('path', ['https://example.com/', '//example.com/', '/x\r\nInjected: yes', '/x#fragment'])
def test_unsafe_paths_rejected(path):
    with pytest.raises(ValueError):
        sa.validate_manifest({'origin': 'http://127.0.0.1:9000', 'checks': [{'kind': 'redirect', 'path': path, 'parameter': 'next'}]})
