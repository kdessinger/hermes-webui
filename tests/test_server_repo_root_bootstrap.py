"""Regression coverage for the managed-runtime server entry point."""
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SERVER = ROOT / "server.py"


def test_server_adds_repo_root_before_api_imports():
    """runpy-based managed launchers must be able to resolve local ``api`` modules."""
    source = SERVER.read_text(encoding="utf-8")
    bootstrap = "_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))"
    first_api_import = "from api.request_logging import emit_request_log"

    assert bootstrap in source
    assert source.index(bootstrap) < source.index(first_api_import)
    assert "sys.path.insert(0, _REPO_ROOT)" in source
    assert "_VENV_SITE_PACKAGES" in source
    assert "sys.path.insert(0, _VENV_SITE_PACKAGES)" in source
    assert "os.listdir(_VENV_LIB)" in source
