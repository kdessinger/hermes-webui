from pathlib import Path


def test_login_probe_does_not_disable_form_on_connectivity_probe_failure():
    src = (Path(__file__).parent.parent / 'static' / 'login.js').read_text(encoding='utf-8')
    assert 'setFormDisabled(true)' not in src, (
        'login connectivity probe should not disable the password field on a transient '
        'network failure; tunnel/proxy users must still be able to attempt login'
    )


def test_login_probe_sends_same_origin_credentials_for_edge_access_proxies():
    src = (Path(__file__).parent.parent / 'static' / 'login.js').read_text(encoding='utf-8')
    assert "fetch('health', { method: 'GET', credentials: 'same-origin' })" in src, (
        'login connectivity probe must send same-origin credentials so edge access '
        'proxies like Cloudflare Access do not block /health and trigger a false '
        'cannot-reach-server warning'
    )
    assert "fetch('health', { method: 'GET', credentials: 'omit' })" not in src, (
        'login connectivity probe must not omit credentials on the health fetch; '
        'doing so drops edge access cookies and creates false tunnel failures'
    )
