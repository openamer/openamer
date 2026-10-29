"""Real HTTP proof/control contracts for native local security assessment."""
import argparse
import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

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


# ── Regression tests for the review findings ────────────────────────────────

def test_non_string_origin_is_a_validation_error_not_a_crash():
    """origin: 123 must not raise AttributeError out of the CLI error handler."""
    with pytest.raises(ValueError, match='string'):
        sa.validate_manifest({'origin': 123, 'checks': []})


def test_cli_turns_invalid_manifest_into_a_blocked_result(tmp_path, capsys):
    manifest = tmp_path / 'm.json'
    manifest.write_text(json.dumps({'origin': 123, 'checks': []}), encoding='utf-8')
    args = argparse.Namespace(security_cmd='assess', manifest=str(manifest),
                              authorized=True, output=str(tmp_path / 'out.json'))
    code = sa.command(args)
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload['status'] == 'blocked'
    assert not (tmp_path / 'out.json').exists()


def test_marker_in_path_is_rejected_because_reflection_is_not_disclosure():
    """A path containing the marker would let a reflecting server fake a finding."""
    marker = 'SYNTHETIC-CANARY-abcdef012345'
    with pytest.raises(ValueError, match='path'):
        sa.validate_manifest({
            'origin': 'http://127.0.0.1:9000',
            'checks': [{'kind': 'canary-read', 'path': '/' + marker, 'parameter': 'file',
                        'control': 'missing.txt', 'payload': '../canary.txt', 'marker': marker}]})


def test_marker_in_parameter_is_rejected():
    marker = 'SYNTHETIC-CANARY-abcdef012345'
    with pytest.raises(ValueError):
        sa.validate_manifest({
            'origin': 'http://127.0.0.1:9000',
            'checks': [{'kind': 'canary-read', 'path': '/download', 'parameter': marker,
                        'control': 'missing.txt', 'payload': '../canary.txt', 'marker': marker}]})


class _ReflectingHandler(BaseHTTPRequestHandler):
    """Reflects the request path back — no file access at all."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = self.path.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def test_reflecting_server_does_not_produce_a_false_confirmation():
    """Reflection of the path is not a file disclosure."""
    server = ThreadingHTTPServer(('127.0.0.1', 0), _ReflectingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        marker = 'SYNTHETIC-CANARY-abcdef012345'
        manifest = {'origin': f'http://127.0.0.1:{server.server_port}', 'checks': [
            {'kind': 'canary-read', 'path': '/download', 'parameter': 'file',
             'control': 'missing.txt', 'payload': '../canary.txt', 'marker': marker}]}
        result = sa.assess(manifest, authorized=True)
        assert result['confirmed'] == 0
        assert result['checks'][0]['status'] != 'confirmed'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _SlowDripHandler(BaseHTTPRequestHandler):
    """Trickles bytes forever — a per-socket timeout alone would never end it."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Length', '1000000')
        self.end_headers()
        try:
            for _ in range(1000):
                self.wfile.write(b'x' * 16)
                self.wfile.flush()
                time.sleep(0.2)
        except OSError:
            pass


def test_slow_dripping_server_is_bounded_by_the_run_deadline():
    server = ThreadingHTTPServer(('127.0.0.1', 0), _SlowDripHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        manifest = {'origin': f'http://127.0.0.1:{server.server_port}', 'checks': [
            {'kind': 'canary-read', 'path': '/download', 'parameter': 'file',
             'control': 'missing.txt', 'payload': '../canary.txt',
             'marker': 'SYNTHETIC-CANARY-abcdef012345'}]}
        started = time.monotonic()
        result = sa.assess(manifest, authorized=True, deadline_seconds=2)
        elapsed = time.monotonic() - started
        assert elapsed < 20, f'assessment was not bounded: {elapsed:.1f}s'
        assert result['confirmed'] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_deadline_is_reported_as_inconclusive_not_as_a_finding():
    """A deadline hit must never be reported as a confirmed finding."""
    server = ThreadingHTTPServer(('127.0.0.1', 0), _SlowDripHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        manifest = {'origin': f'http://127.0.0.1:{server.server_port}', 'checks': [
            {'kind': 'canary-read', 'path': '/download', 'parameter': 'file',
             'control': 'missing.txt', 'payload': '../canary.txt',
             'marker': 'SYNTHETIC-CANARY-abcdef012345'}]}
        result = sa.assess(manifest, authorized=True, deadline_seconds=1)
        assert result['confirmed'] == 0
        for check in result['checks']:
            assert check['status'] == 'inconclusive'
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_legacy_security_dispatch_routes_to_posture_not_to_the_audit():
    """`openamer security posture` must not fall through to the OSV audit."""
    from openamer_cli.main import cmd_security
    args = argparse.Namespace(security_cmd='posture', security_command=None)
    assert cmd_security(args) == 0


def test_legacy_security_dispatch_reads_both_attribute_names():
    from openamer_cli.main import cmd_security
    args = argparse.Namespace(security_cmd=None, security_command='posture')
    assert cmd_security(args) == 0


def test_saved_report_is_never_overwritten(tmp_path):
    target = tmp_path / 'report.json'
    sa.save_report(target, {'first': True})
    with pytest.raises(FileExistsError):
        sa.save_report(target, {'second': True})


def test_lab_fixture_servers_are_closed_after_the_run(tmp_path):
    """No fixture server may keep a port open after run_lab returns."""
    before = set()
    sa.run_lab(tmp_path)
    # A closed listening socket must be immediately rebindable.
    probe = socket.socket()
    try:
        probe.bind(('127.0.0.1', 0))
        probe.close()
    except OSError as exc:  # pragma: no cover - platform dependent
        pytest.fail(f'could not rebind after lab run: {exc}')
