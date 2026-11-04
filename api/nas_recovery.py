"""Fixed, authenticated same-origin bridge to Kenn's read-only NAS dashboard.

Called only after server.check_auth. Never accepts an upstream URL, forwards
credentials, follows redirects, or exposes recovery commands.
"""
import http.client
import re

PREFIX = '/apps/nas-recovery/'
ASSET = re.compile(r'assets/[A-Za-z0-9_-]+\.(?:js|css)\Z')
MAX_BYTES = 8 * 1024 * 1024


def handle_nas_recovery(handler, parsed):
    if not parsed.path.startswith(PREFIX):
        return False
    tail = parsed.path[len(PREFIX):]
    if parsed.query or not (tail in ('', 'index.html', 'api/status') or ASSET.fullmatch(tail)):
        status, body, content_type = 404, b'Not found', 'text/plain'
    else:
        conn = http.client.HTTPConnection('10.20.30.21', 41177, timeout=5)
        try:
            conn.request('GET', '/' + tail)
            response = conn.getresponse()
            body = response.read(MAX_BYTES + 1)
            if response.status != 200 or len(body) > MAX_BYTES:
                raise OSError('Dashboard unavailable')
            status = 200
            content_type = response.getheader('Content-Type', 'application/octet-stream')
            if tail in ('', 'index.html'):
                body = body.replace(b'"/assets/', b'"' + PREFIX.encode() + b'assets/')
            elif tail.endswith('.js'):
                body = body.replace(b'/api/status', PREFIX.encode() + b'api/status')
        except (OSError, http.client.HTTPException):
            status, body, content_type = 503, b'NAS dashboard temporarily unavailable', 'text/plain'
        finally:
            conn.close()
    handler.send_response(status)
    handler.send_header('Content-Type', content_type)
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'self'; object-src 'none'; base-uri 'none'")
    handler.end_headers()
    handler.wfile.write(body)
    return True
