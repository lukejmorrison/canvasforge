"""The Intel .app must ship pairing modules, vendored QR, and the LAN fallback."""

import sys
from pathlib import Path

import mobile_sync

ROOT = Path(__file__).resolve().parents[1]
SPEC = (ROOT / "canvasforge.spec").read_text(encoding="utf-8")


def test_spec_hides_pairing_modules():
    for name in (
        "mobile_sync",
        "mobile_qr",
        "macos_restorable",
        "vendor.segno",
        "vendor.segno.encoder",
    ):
        assert f'"{name}"' in SPEC


def test_spec_ships_vendor_and_html_fallback_not_flutter_tree():
    assert 'ROOT / "vendor"' in SPEC
    assert "MOBILE_FALLBACK" in SPEC
    assert "index.html" in SPEC
    assert "do not ship the Flutter tree" in SPEC
    assert 'ROOT / "mobile/app"' not in SPEC


def test_companion_fallback_files_exist():
    mobile = ROOT / "mobile"
    for name in ("index.html", "app.js", "style.css", "manifest.webmanifest"):
        assert (mobile / name).is_file(), name


def test_resource_root_uses_pyinstaller_meipass(monkeypatch, tmp_path):
    mobile = tmp_path / "mobile"
    mobile.mkdir()
    (mobile / "index.html").write_text("<html>paired</html>", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert mobile_sync.resource_root() == tmp_path
    assert mobile_sync.companion_dir() == mobile
    assert (mobile_sync.companion_dir() / "index.html").read_text(encoding="utf-8") == (
        "<html>paired</html>"
    )


def test_resource_root_is_checkout_when_not_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert mobile_sync.resource_root() == ROOT
    assert mobile_sync.companion_dir() == ROOT / "mobile"
