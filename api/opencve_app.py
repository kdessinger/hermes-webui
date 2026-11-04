"""Authenticated fixed-target OpenCVE bridge; invoked after WebUI auth only."""
import http.client
from http.cookies import SimpleCookie
from urllib.parse import unquote, urlsplit

PREFIX = '/apps/opencve'
UPSTREAM = ('10.20.30.113', 8095)
MAX_BODY = 2 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024
COOKIE_NAMES = {'opencve_session', 'opencve_csrf'}


def handle_opencve(handler, parsed):
    if parsed.path != PREFIX and not parsed.path.startswith(PREFIX + '/'):
        return False
    def reply(status, body):
        handler.send_response(status)
        handler.send_header('Content-Type', 'text/plain; charset=utf-8')
        handler.send_header('Content-Length', str(len(body)))
        handler.send_header('Cache-Control', 'no-store')
        handler.end_headers()
        handler.wfile.write(body)
        return True
    tail = parsed.path[len(PREFIX):] or '/'
    decoded = unquote(tail)
    if any(x in decoded for x in ('\\', '\r', '\n', '\x00')) or any(p in ('.', '..') for p in decoded.split('/')) or tail.startswith('//'):
        return reply(400, b'Invalid app path')
    method = handler.command
    if method not in ('GET', 'POST'):
        return reply(405, b'Method not supported')
    if handler.headers.get('Transfer-Encoding'):
        return reply(400, b'Transfer encoding not supported')
    try:
        length = int(handler.headers.get('Content-Length', '0'))
    except ValueError:
        return reply(400, b'Invalid content length')
    if not 0 <= length <= MAX_BODY:
        return reply(413, b'Request too large')
    headers = {'Host': 'hermes.kdessinger.com', 'X-Forwarded-Proto': 'https', 'Accept-Encoding': 'identity'}
    # Never forward WebUI, Cloudflare Access, authorization or other app cookies.
    cookies = SimpleCookie()
    try:
        cookies.load(handler.headers.get('Cookie', ''))
    except Exception:
        return reply(400, b'Invalid cookies')
    selected = [f'{k}={v.value}' for k, v in cookies.items() if k in COOKIE_NAMES]
    if selected:
        headers['Cookie'] = '; '.join(selected)
    for name in ('Content-Type', 'Accept', 'Origin', 'Referer', 'X-CSRFToken'):
        if handler.headers.get(name):
            headers[name] = handler.headers[name]
    if method == 'POST':
        # Do not turn a hostile Origin into a trusted one. Django also enforces
        # its own independent, app-scoped CSRF token on every form submission.
        if handler.headers.get('Origin') not in (None, 'https://hermes.kdessinger.com'):
            return reply(403, b'Invalid app origin')
    body = handler.rfile.read(length) if length else None
    conn = http.client.HTTPConnection(*UPSTREAM, timeout=30)
    try:
        conn.request(method, tail + ('?' + parsed.query if parsed.query else ''), body=body, headers=headers)
        response = conn.getresponse()
        data = response.read(MAX_RESPONSE + 1)
        if len(data) > MAX_RESPONSE:
            return reply(502, b'App response too large')
        location = response.getheader('Location')
        if location:
            u = urlsplit(location)
            if u.netloc and u.netloc not in ('hermes.kdessinger.com', '10.20.30.113:8095'):
                return reply(502, b'Unexpected app redirect')
            path = u.path or '/'
            if not path.startswith(PREFIX + '/'):
                path = PREFIX + '/' + path.lstrip('/')
            location = path + ('?' + u.query if u.query else '')
        handler.send_response(response.status)
        for name in ('Content-Type', 'Content-Disposition'):
            value = response.getheader(name)
            if value:
                handler.send_header(name, value)
        if location:
            handler.send_header('Location', location)
        for name, value in response.getheaders():
            if name.lower() == 'set-cookie':
                c = SimpleCookie(); c.load(value)
                for key, morsel in c.items():
                    if key in COOKIE_NAMES:
                        morsel['path'] = PREFIX + '/'
                        morsel['secure'] = True
                        morsel['samesite'] = 'Lax'
                        morsel['domain'] = ''
                        handler.send_header('Set-Cookie', morsel.OutputString())
        handler.send_header('Content-Length', str(len(data)))
        handler.send_header('Cache-Control', 'no-store')
        handler.send_header('X-Content-Type-Options', 'nosniff')
        handler.send_header('X-Frame-Options', 'SAMEORIGIN')
        handler.end_headers()
        handler.wfile.write(data)
        return True
    except (OSError, http.client.HTTPException):
        return reply(503, b'OpenCVE temporarily unavailable')
    finally:
        conn.close()
