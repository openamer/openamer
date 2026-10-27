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
import uuid
from urllib.parse import parse_qs, urlencode, urlsplit

MAX_CHECKS = 10
MAX_BODY = 65536


def validate_manifest(manifest):
    if not isinstance(manifest, dict):
        raise ValueError('Manifest must be an object')
    origin = manifest.get('origin', '')
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
            if check['marker'] in check['payload'] or check['marker'] in check['control']:
                raise ValueError('Canary marker must not be present in the request inputs')
    return parsed


def exchange(origin, path):
    """One direct connection, no proxy or redirect logic. Evidence excludes cookies."""
    parsed = urlsplit(origin)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=3)
    request = f'GET {path} HTTP/1.1\r\nHost: {parsed.netloc}\r\nConnection: close\r\n\r\n'
    try:
        connection.putrequest('GET', path, skip_host=True, skip_accept_encoding=True)
        connection.putheader('Host', parsed.netloc)
        connection.putheader('Connection', 'close')
        connection.endheaders()
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        headers = {key.lower(): value for key, value in response.getheaders()
                   if key.lower() in {'location', 'content-type', 'content-length'}}
        return {
            'request': request,
            'response': {'status': response.status, 'headers': headers,
                         'body': body[:MAX_BODY].decode('utf-8', errors='replace'),
                         'body_sha256': hashlib.sha256(body[:MAX_BODY]).hexdigest(),
                         'truncated': len(body) > MAX_BODY},
        }
    finally:
        connection.close()


def assess(manifest, *, authorized=False):
    if not authorized:
        raise ValueError('Explicit target authorization is required')
    validate_manifest(manifest)
    origin = manifest['origin']
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
                item['exchanges'].append(exchange(origin, path))
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
                        'Request/response evidence is application-level, not a packet capture.'],
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
            class Handler(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def do_GET(self):
                    parsed = urlsplit(self.path)
                    query = parse_qs(parsed.query)
                    if parsed.path == '/redirect':
                        dest = query.get('next', ['/'])[0]
                        if fixed and (not dest.startswith('/') or dest.startswith('//')):
                            self.send_error(400)
                            return
                        self.send_response(302)
                        self.send_header('Location', dest)
                        self.end_headers()
                    elif parsed.path == '/download':
                        candidate = (public / query.get('file', ['missing.txt'])[0]).resolve()
                        # Even the vulnerable fixture cannot access outside synthetic data.
                        if not candidate.is_relative_to(root) or (fixed and not candidate.is_relative_to(public)):
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

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
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
