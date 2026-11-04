"""Dispatch for the WebUI's authenticated in-app bridges.

Three extensions expose their own same-origin surface under ``/apps/``:
``external-apps`` (the configurable app slots), ``nas-recovery`` and
``opencve``. Each bridge authenticates itself, validates a fixed target, and
returns ``True`` when it has handled the request.

Kept out of ``server.py`` so that entry point stays inside upstream's
line-count budget (``tests/test_sprint10.py::test_server_py_under_760_lines``)
and so the GET and write paths cannot drift apart: both call the same helper.
"""

from __future__ import annotations

from typing import Any


def handle_app_bridges(handler: Any, parsed: Any) -> bool:
    """Route a request to the app bridges; True when one of them handled it.

    Must be called AFTER authentication. The ``/api/external-apps`` write path
    additionally requires a CSRF token, because it mutates server-side slot
    configuration.
    """
    from api.external_apps import handle_external_apps
    from api.opencve_app import handle_opencve

    if handle_external_apps(handler, parsed):
        return True
    if handle_opencve(handler, parsed):
        return True
    return False


def require_external_apps_csrf(handler: Any, parsed: Any, j: Any) -> bool:
    """Enforce CSRF on the ``/api/external-apps`` write path.

    Returns True when the request may proceed. On failure it sends the 403 and
    returns False, so the caller must return immediately.
    """
    if parsed.path != "/api/external-apps":
        return True
    from api.routes import _check_csrf

    if not _check_csrf(handler):
        j(handler, {"error": "CSRF validation failed"}, status=403)
        return False
    return True
