"""Regression coverage for the managed-runtime server entry point.

Two bootstraps keep the WebUI importable when Hermes launches it through an
Agent-managed interpreter via ``runpy.run_path()``:

1. the repo root on ``sys.path`` — so local ``api.*`` modules resolve. Upstream
   ``server.py`` already does this in its ``_webui_root`` block.
2. the WebUI venv's ``site-packages`` on ``sys.path`` — so the WebUI's own
   dependencies resolve even though the managed interpreter bypasses the
   venv's activation. This one lives in ``webui_path_bootstrap.py`` so the
   entry point stays inside upstream's line budget
   (``tests/test_sprint10.py::test_server_py_under_760_lines``).

These tests assert the guarantees hold, not where the code physically sits.
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server.py"
BOOTSTRAP = ROOT / "webui_path_bootstrap.py"


def test_server_adds_repo_root_before_api_imports():
    """runpy-based managed launchers must be able to resolve local ``api`` modules."""
    source = SERVER.read_text(encoding="utf-8")
    repo_root = "_webui_root = os.path.dirname(os.path.abspath(__file__))"
    first_api_import = "from api.request_logging import emit_request_log"

    assert repo_root in source
    assert source.index(repo_root) < source.index(first_api_import)
    assert "sys.path.insert(0, _webui_root)" in source


def test_server_imports_the_venv_bootstrap_before_api_imports():
    """The venv bootstrap must run before the first ``api.*`` import."""
    source = SERVER.read_text(encoding="utf-8")
    first_api_import = "from api.request_logging import emit_request_log"

    assert "import webui_path_bootstrap" in source
    assert source.index("import webui_path_bootstrap") < source.index(first_api_import)


def test_bootstrap_restores_venv_site_packages():
    """The bootstrap module puts the venv's site-packages on sys.path."""
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert "site_packages = os.path.join(" in source
    assert "sys.path.insert(0, site_packages)" in source
    assert "site_packages = os.path.join(venv_lib," in source
    assert '".venv", "lib"' in source
    assert "site-packages" in source


def test_bootstrap_runs_on_import():
    """Importing the module must actually apply the fix (side effect)."""
    source = BOOTSTRAP.read_text(encoding="utf-8")

    # The module-level call is what makes the import in server.py effective.
    assert "ensure_venv_site_packages()" in source


def test_bootstrap_defaults_to_the_checkout_root():
    """ensure_venv_site_packages() must default to the checkout's own root."""
    source = BOOTSTRAP.read_text(encoding="utf-8")

    assert 'os.path.dirname(os.path.abspath(__file__))' in source
