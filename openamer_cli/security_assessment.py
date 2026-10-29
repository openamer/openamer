"""Bounded, opt-in HTTP security assessment for local staging applications.

No crawling, DNS, redirect following, credentials, shell payloads or automatic fixes.
Confirmed means a repeatable effect plus a discriminating control, not independent review.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import tempfile
import threading
import time
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

MAX_CHECKS = 10
MAX_BODY = 65536
SOCKET_TIMEOUT = 3
# Whole-run budget: a per-socket timeout alone does not bound a slow-drip server.
RUN_DEADLINE_SECONDS = 60


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')
    origin = manifest.get('origin', '')
    if not isinstance(origin, str):
        raise ValueError('Origin must be a string')
    parsed = urlsplit(origin)
    try:
        address = ipaddress.ip_address(parsed.hostname or '')
        port = parsed.port
    except ValueError as exc:
        raise ValueError('Origin must use a literal loopback IP') from exc
    if (parsed.scheme != 'http' or not address.is_loopback or address.version != 4
            or not port or parsed.username or parsed.password or parsed.path
            or parsed.query or parsed.fragment):
        raise ValueError('Only exact http://127.x.x.x:port origins are supported')
    checks = manifest.get('checks')
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS:
        raise ValueError('Provide between 1 and 10 checks')
    for check in checks:
        if not isinstance(check, dict) or check.get('kind') not in {'redirect', 'canary-read'}:
            raise ValueError('Supported check kinds: redirect, canary-read')
        path = check.get('path', '')
        parameter = check.get('parameter', '')
        if (not isinstance(path, str) or not path.startswith('/') or path.startswith('//')
                or any(ord(c) < 33 or ord(c) > 126 for c in path)
                or any(c in path for c in '?#\\')):
            raise ValueError('Check path must be an ASCII origin-relative path without query or fragment')
        if not isinstance(parameter, str) or not parameter.isidentifier() or len(parameter) > 64:
            raise ValueError('Parameter must be a short identifier')
        if check['kind'] == 'canary-read':
            for key in ('control', 'payload', 'marker'):
                value = check.get(key)
                if not isinstance(value, str) or not 8 <= len(value) <= 1024:
                    raise ValueError(f'canary-read requires {key} (8..1024 characters)')
            # The marker must not be derivable from ANY request input, otherwise a
            # server that merely reflects the path or query would look like a
            # disclosure (a false 'confirmed' with no file access at all).
            for source, label in ((path, 'path'), (parameter, 'parameter'),
                                  (check['control'], 'control'), (check['payload'], 'payload')):
                if check['marker'] in source:
                    raise ValueError(f'Canary marker must not be present in the {label}')
    return parsed


def exchange(origin, path, deadline=None):
    """One direct connection, no proxy or redirect logic. Evidence excludes cookies."""
    parsed = urlsplit(origin)
    timeout = SOCKET_TIMEOUT
    if deadline is not None:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Assessment deadline exceeded before request')
        timeout = min(SOCKET_TIMEOUT, remaining)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
    request = f'GET {path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nConnection: close\r\n\r\n'
    try:
        connection.putrequest('GET', path, skip_host=True, skip_accept_encoding=True)
        connection.putheader('Host', parsed.netloc)
        connection.putheader('Connection', 'close')
        connection.endheaders()
        response = connection.getresponse()
        body, read_error = _read_body(response, deadline)
        headers = {key.lower(): value for key, value in response.getheaders()
                   if key.lower() in {'location', 'content-type', 'content-length'}}
        return {
            'request': request,
            'request_is_reconstructed': True,
            'response': {'status': response.status, 'headers': headers,
                         'body': body[:MAX_BODY].decode('utf-8', errors='replace'),
                         'body_sha256': hashlib.sha256(body[:MAX_BODY]).hexdigest(),
                         'truncated': len(body) > MAX_BODY or read_error is not None,
                         'read_error': read_error},
        }
    finally:
        connection.close()


def _read_body(response, deadline=None):
    """Read the body under a hard wall-clock budget.

    A per-socket timeout only bounds a single blocking read: a server that
    trickles bytes can keep a plain ``read()`` alive indefinitely. Reading in
    bounded chunks and re-checking the deadline bounds the whole exchange.
    """
    chunks = []
    total = 0
    error = None
    while True:
        if deadline is not None and time.monotonic() >= deadline:
            error = 'deadline exceeded while reading body'
            break
        try:
            chunk = response.read1(16384)
        except (TimeoutError, OSError) as exc:
            error = f'{type(exc).__name__}: {exc}'
            break
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_BODY:
            break
    return b''.join(chunks)[:MAX_BODY + 1], error


def assess(manifest, *, authorized=False, deadline_seconds=RUN_DEADLINE_SECONDS):
    if not authorized:
        raise ValueError('Explicit target authorization is required')
    validate_manifest(manifest)
    origin = manifest['origin']
    deadline = time.monotonic() + deadline_seconds
    results = []
    for check in manifest['checks']:
        item = {'kind': check['kind'], 'path': check['path'], 'parameter': check['parameter'],
                'status': 'inconclusive', 'exchanges': []}
        if check['kind'] == 'redirect':
            control = '/openamer-control-' + uuid.uuid4().hex
            payload = 'https://openamer-probe.invalid/' + uuid.uuid4().hex
        else:
            control, payload = check['control'], check['payload']
        try:
            for value in (control, payload, payload):
                path = check['path'] + '?' + urlencode({check['parameter']: value})
                item['exchanges'].append(exchange(origin, path, deadline=deadline))
            baseline, first, repeat = [e['response'] for e in item['exchanges']]
            if any(r['truncated'] or r['status'] >= 500 for r in (baseline, first, repeat)):
                item['reason'] = 'Truncated body or server error; no conclusion'
            elif check['kind'] == 'redirect':
                def redirects(r, location):
                    return r['status'] in {301, 302, 303, 307, 308} and r['headers'].get('location') == location
                if not redirects(baseline, control):
                    item['reason'] = 'Benign redirect control did not succeed'
                else:
                    item['status'] = ('confirmed' if redirects(first, payload) and redirects(repeat, payload)
                                      else 'not_reproduced')
                    item['cwe'] = 'CWE-601'
            else:
                marker = check['marker']
                def disclosed(r):
                    return r['status'] == 200 and marker in r['body']
                if marker in baseline['body'] or baseline['status'] not in {200, 400, 403, 404}:
                    item['reason'] = 'Control does not discriminate protected canary access'
                else:
                    item['status'] = ('confirmed' if disclosed(first) and disclosed(repeat)
                                      else 'not_reproduced')
                    item['cwe'] = 'CWE-200'
                    item['reason'] = 'Canary disclosure check; root cause needs manual review'
        except (OSError, http.client.HTTPException, ValueError) as exc:
            item['reason'] = f'{type(exc).__name__}: {exc}'
        results.append(item)
    return {
        'schema_version': 1, 'measured_at': datetime.now(timezone.utc).isoformat(),
        'origin': origin, 'checks': results,
        'confirmed': sum(c['status'] == 'confirmed' for c in results),
        'inconclusive': sum(c['status'] == 'inconclusive' for c in results),
        'independently_verified': False,
        'limitations': ['Only configured GET endpoints and parameters are assessed.',
                        'No finding is not a security certificate.',
                        'Local IPv4 HTTP staging only; no authenticated testing.',
                        'Evidence may contain application data. Keep reports private.',
                        'Request/response evidence is application-level, not a packet capture.',
                        'The recorded request text is reconstructed by the client, not captured.'],
    }


def save_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never silently overwrite prior evidence.
    with path.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')


def run_lab(output):
    """Real HTTP + filesystem fixture, restricted to synthetic temporary data."""
    reports = {}
    with tempfile.TemporaryDirectory(prefix='openamer-assessment-') as temp:
        root = Path(temp)
        public = root / 'public'
        public.mkdir()
        marker = 'SYNTHETIC-CANARY-' + uuid.uuid4().hex
        (root / 'canary.txt').write_text(marker, encoding='utf-8')
        for fixed in (False, True):
            # The mode is bound per server (not read from a loop variable) so a
            # request thread that outlives the server can never change meaning
            # halfway through a response.
            class Handler(BaseHTTPRequestHandler):
                is_fixed = fixed
                # A stuck client must not be able to hang server_close(): the
                # fixture waits for its request threads (block_on_close), so
                # each one needs its own socket timeout.
                timeout = 5

                def log_message(self, *args):
                    pass

                def do_GET(self):
                    parsed = urlsplit(self.path)
                    query = parse_qs(parsed.query)
                    if parsed.path == '/redirect':
                        dest = query.get('next', ['/'])[0]
                        if self.is_fixed and (not dest.startswith('/') or dest.startswith('//')):
                            self.send_error(400)
                            return
                        self.send_response(302)
                        self.send_header('Location', dest)
                        self.end_headers()
                    elif parsed.path == '/download':
                        candidate = (public / query.get('file', ['missing.txt'])[0]).resolve()
                        # Even the vulnerable fixture cannot access outside synthetic data.
                        if (not candidate.is_relative_to(root)
                                or (self.is_fixed and not candidate.is_relative_to(public))):
                            self.send_error(403)
                            return
                        if not candidate.is_file():
                            self.send_error(404)
                            return
                        data = candidate.read_bytes()
                        self.send_response(200)
                        self.send_header('Content-Length', str(len(data)))
                        self.end_headers()
                        self.wfile.write(data)
                    else:
                        self.send_error(404)

            class Server(ThreadingHTTPServer):
                # Wait for in-flight request threads on close, so no thread can
                # outlive the fixture and touch a deleted temporary directory.
                daemon_threads = False
                block_on_close = True

            server = Server(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                manifest = {'origin': f'http://127.0.0.1:{server.server_port}', 'checks': [
                    {'kind': 'redirect', 'path': '/redirect', 'parameter': 'next'},
                    {'kind': 'canary-read', 'path': '/download', 'parameter': 'file',
                     'control': 'missing.txt', 'payload': '../canary.txt', 'marker': marker},
                ]}
                reports['fixed' if fixed else 'vulnerable'] = assess(manifest, authorized=True)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)
    reports['verified'] = (reports['vulnerable']['confirmed'] == 2
                           and all(c['status'] == 'not_reproduced' for c in reports['fixed']['checks']))
    save_report(Path(output) / 'lab.json', reports)
    return reports


def command(args):
    try:
        if args.security_cmd == 'lab':
            result = run_lab(args.output)
            print(json.dumps({'verified': result['verified'],
                              'vulnerable_confirmed': result['vulnerable']['confirmed'],
                              'fixed_confirmed': result['fixed']['confirmed'],
                              'report': str(Path(args.output) / 'lab.json')}, indent=2))
            return 0 if result['verified'] else 2
        if not args.authorized:
            raise ValueError('Explicit target authorization is required (--authorized)')
        manifest = json.loads(Path(args.manifest).read_text(encoding='utf-8'))
        result = assess(manifest, authorized=True)
        save_report(args.output, result)
        print(json.dumps(result, indent=2))
        return 2 if result['inconclusive'] else (1 if result['confirmed'] else 0)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}))
        return 2
