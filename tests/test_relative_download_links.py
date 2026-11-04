"""Exercise real final-message renderer for authenticated download links."""
from html.parser import HTMLParser
import pytest
from tests.test_renderer_js_behaviour import driver_path, _render

class Anchors(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs=[]
        self.feed(html)
    def handle_starttag(self, tag, attrs):
        if tag=='a':
            self.hrefs.extend(v for k,v in attrs if k=='href')

@pytest.mark.parametrize('prefix',['','- **Password:** ','> Download: ','| File |\n| --- |\n| '])
@pytest.mark.parametrize('destination',[
    '/api/file/raw?session_id=fixture&path=notes%2Fhello.txt&download=1',
    'api/file/raw?session_id=fixture&path=notes%2Fhello.txt&download=1',
])
def test_download_link_survives_final_render(driver_path,prefix,destination):
    out=_render(driver_path,prefix+'[Download file]('+destination+')')
    assert Anchors(out).hrefs==[destination]
    assert '[Download file]' not in out

@pytest.mark.parametrize('destination',[
    '//evil.example/api/file/raw','/\\evil.example/api/file/raw',
    '/api/\\evil.example','/api/\tevil.example','javascript:alert%281%29',
    'data:text/html,evil','vbscript:evil',
])
def test_unsafe_relative_links_do_not_become_anchors(driver_path,destination):
    assert not Anchors(_render(driver_path,'[Download]('+destination+')')).hrefs

def test_raw_protocol_relative_html_remains_blocked(driver_path):
    assert not Anchors(_render(driver_path,'<a href="//evil.example/api/file/raw">x</a>')).hrefs
