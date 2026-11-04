"""Fixed-target proxy tests; no credentials or real user data."""
from io import BytesIO
from urllib.parse import urlsplit
from unittest.mock import patch
from api.opencve_app import handle_opencve

class Handler:
    command='GET'
    def __init__(self,headers=None):
        self.headers=headers or {};self.rfile=BytesIO();self.wfile=BytesIO();self.sent=[]
    def send_response(self,status):self.status=status
    def send_header(self,k,v):self.sent.append((k,v))
    def end_headers(self):pass

class Response:
    status=200
    def read(self,n):return b'ok'
    def getheader(self,k,default=None):return {'Content-Type':'text/plain'}.get(k,default)
    def getheaders(self):return [('Set-Cookie','opencve_session=x; Path=/'),('Set-Cookie','webui_session=evil; Path=/')]


def test_only_fixed_target_and_app_cookies_forwarded():
    h=Handler({'Cookie':'opencve_session=abc; webui_session=private; CF_Authorization=secret'})
    with patch('api.opencve_app.http.client.HTTPConnection') as cls:
        cls.return_value.getresponse.return_value=Response()
        assert handle_opencve(h,urlsplit('/apps/opencve/cve/?q=php'))
        cls.assert_called_once_with('10.20.30.113',8095,timeout=30)
        args,kw=cls.return_value.request.call_args
        assert args==('GET','/cve/?q=php')
        assert kw['headers']['Cookie']=='opencve_session=abc'
    cookies=[v for k,v in h.sent if k=='Set-Cookie']
    assert len(cookies)==1 and 'Path=/apps/opencve/' in cookies[0] and 'Secure' in cookies[0]


def test_other_routes_untouched():
    assert handle_opencve(Handler(),urlsplit('/apps/nas-recovery/')) is False


def test_traversal_rejected():
    for path in ['/apps/opencve/%2e%2e/api/auth','/apps/opencve//evil','/apps/opencve/%5cevil']:
        h=Handler();assert handle_opencve(h,urlsplit(path));assert h.status==400


def test_hostile_origin_rejected():
    h=Handler({'Origin':'https://evil.example'});h.command='POST'
    assert handle_opencve(h,urlsplit('/apps/opencve/login/'));assert h.status==403
