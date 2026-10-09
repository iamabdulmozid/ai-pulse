"""T-01 acceptance: shell boots, theme tokens exist."""
from pathlib import Path

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


def test_shell_boots(client):
    resp = client.get("/healthz/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "as_of" in data and data["as_of"]


def test_login_page_renders(client):
    resp = client.get("/login/")
    assert resp.status_code == 200
    assert b"AI Pulse" in resp.content


def test_overview_requires_login(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/login/" in resp["Location"]


TOKENS = ["--surface", "--border", "--text", "--accent", "--ok", "--watch",
          "--risk", "--crit", "--late", "--knit", "--link", "--pack", "--ai"]


def test_theme_tokens():
    import re

    raw = (Path(settings.BASE_DIR) / "static" / "css" / "theme-tokens.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", raw, flags=re.DOTALL)  # strip comments
    assert ':root[data-theme="light"]' in css
    assert ':root[data-theme="dark"]' in css
    light_block = css.split(':root[data-theme="dark"]')[0]
    dark_block = css.split(':root[data-theme="dark"]', 1)[1]
    for tok in TOKENS:
        assert f"{tok}:" in light_block, f"{tok} missing from light theme"
        assert f"{tok}:" in dark_block, f"{tok} missing from dark theme"
