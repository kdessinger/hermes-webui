"""Regression tests for the public Agentarium concept-art asset route."""
from __future__ import annotations

import io
from types import SimpleNamespace


class _Handler:
    def __init__(self):
        self.status = None
        self.headers = {}
        self.response_headers = {}
        self.wfile = io.BytesIO()

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass


def test_public_agentarium_concept_art_route_serves_ship_image():
    from api import routes

    handler = _Handler()
    handled = routes._handle_agentarium_concept_art(
        handler,
        SimpleNamespace(
            path="/assets/concept-art/ship/ship-overview-cross-section.png",
            query="",
        ),
    )

    assert handled is True
    assert handler.status == 200
    assert handler.response_headers["Content-Type"] == "image/png"
    assert int(handler.response_headers["Content-Length"]) > 1_000_000
    assert handler.wfile.getvalue().startswith(b"\x89PNG\r\n\x1a\n")


def test_public_agentarium_concept_art_route_rejects_path_traversal():
    from api import routes

    handler = _Handler()
    handled = routes._handle_agentarium_concept_art(
        handler,
        SimpleNamespace(path="/assets/concept-art/../AGENTS.md", query=""),
    )

    assert handled is None
    assert handler.status == 404


def test_public_agentarium_concept_art_route_is_registered_before_fallback():
    from pathlib import Path

    source = (Path(__file__).parent.parent / "api" / "routes.py").read_text(encoding="utf-8")
    assert 'parsed.path.startswith("/assets/concept-art/")' in source


def test_concept_art_assets_do_not_require_the_webui_session_cookie(monkeypatch):
    """Sandboxed inline HTML cannot carry the WebUI's authenticated cookie.

    Cloudflare Access remains the internet-facing boundary; this only avoids a
    second, cookie-based redirect for the fixed public concept-art bundle.
    """
    from api import auth

    monkeypatch.setattr(auth, "is_auth_enabled", lambda: True)
    handler = _Handler()
    allowed = auth.check_auth(
        handler,
        SimpleNamespace(path="/assets/concept-art/rooms/archives.png", query=""),
    )

    assert allowed is True
    assert handler.status is None
