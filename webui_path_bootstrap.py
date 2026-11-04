"""WebUI dependency-path bootstrap for Hermes-managed interpreters.

Hermes may launch the WebUI through an Agent-managed interpreter that runs
``server.py`` via ``runpy.run_path()``. Two things then go wrong:

1. ``runpy.run_path()`` does not put the script's directory on ``sys.path``, so
   the local ``api.*`` imports are not resolvable. Upstream ``server.py``
   already restores the repo root for this (see its ``_webui_root`` block).
2. The managed interpreter bypasses the WebUI venv's activation, so the
   WebUI's own dependencies (PyYAML/ruamel, aiohttp, and the rest) are not on
   the path. The managed Python has its own dependency set, which does not
   necessarily include them.

This module restores the WebUI's ``.venv`` site-packages on ``sys.path`` so the
WebUI's dependencies resolve under a managed interpreter too, without requiring
a second globally-installed dependency set.

Kept out of ``server.py`` deliberately: upstream enforces a line-count budget
on that file (``tests/test_sprint10.py::test_server_py_under_760_lines``), and
the bootstrap belongs with the rest of the startup path rather than growing the
entry point.
"""

from __future__ import annotations

import os
import sys


def ensure_venv_site_packages(repo_root: str | None = None) -> str | None:
    """Put the WebUI venv's site-packages on ``sys.path``; return the path used.

    The interpreter's own version directory is preferred (``python3.11``), but a
    managed interpreter may differ from the venv's, so fall back to the newest
    ``python*`` directory under ``.venv/lib`` when the exact one is absent.
    """
    root = repo_root or os.path.dirname(os.path.abspath(__file__))
    venv_lib = os.path.join(root, ".venv", "lib")
    if not os.path.isdir(venv_lib):
        return None

    site_packages = os.path.join(
        venv_lib,
        f"python{sys.version_info.major}.{sys.version_info.minor}",
        "site-packages",
    )
    if not os.path.isdir(site_packages):
        candidates = sorted(
            name for name in os.listdir(venv_lib) if name.startswith("python")
        )
        if not candidates:
            return None
        site_packages = os.path.join(venv_lib, candidates[-1], "site-packages")

    if not os.path.isdir(site_packages):
        return None
    if site_packages not in sys.path:
        sys.path.insert(0, site_packages)
    return site_packages


ensure_venv_site_packages()
