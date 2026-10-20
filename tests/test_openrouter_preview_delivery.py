"""Preview HTML must not reuse the pre-preview cached catalog script."""
from pathlib import Path
import re


def test_preview_assets_and_button_style():
    html = (Path(__file__).resolve().parents[1] / 'static/index.html').read_text()
    assert 'openrouter-tts.js?v=__WEBUI_VERSION__-preview-2' in html
    for name in ('settingsOpenRouterPreview', 'settingsOpenRouterRefresh'):
        tag = re.search(r'<button\b[^>]*id="' + name + r'"[^>]*>', html).group()
        assert 'class="btn primary"' in tag
