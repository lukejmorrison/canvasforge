import json
import struct
import zlib
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QLabel

from main import PreferencesDialog
from mobile_qr import choose_version, qr_has_finder_patterns, qr_matrix
from mobile_sync import (
    DEFAULT_PORT,
    MobileSyncService,
    PairingStore,
    build_pairing_payload,
    parse_pairing_link,
    pairing_qr_text,
    pasteable_pairing_code,
    save_grab_to_library,
    security_code_from_token,
    sniff_image_suffix,
)


def _png_bytes(width=2, height=2, rgb=(30, 80, 200)) -> bytes:
    """Minimal valid PNG so upload tests do not need Qt or Pillow."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return b"".join(
        [
            b"\x89PNG\r\n\x1a\n",
            chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)),
            chunk(b"IDAT", zlib.compress(raw)),
            chunk(b"IEND", b""),
        ]
    )


def test_security_code_is_stable_and_readable():
    token = "a" * 32
    code = security_code_from_token(token)
    assert code == security_code_from_token(token)
    assert "-" in code
    assert len(code) == 9
    assert code != security_code_from_token("b" * 32)


def test_pairing_formats_match_flutter_client_examples():
    """Keep the Dart PairingLink.parse cases in lock-step with the desktop."""
    qr = "http://192.168.1.20:17831/?pair=deadbeefcafebabe0123456789abcdef"
    pasted = "192.168.1.20:17831#deadbeefcafebabe0123456789abcdef"
    from_qr = parse_pairing_link(qr)
    from_paste = parse_pairing_link(pasted)
    assert from_qr["token"] == from_paste["token"] == "deadbeefcafebabe0123456789abcdef"
    assert from_qr["url"] == from_paste["url"] == "http://192.168.1.20:17831"


def test_pairing_payload_and_pasteable_code():
    payload = build_pairing_payload("deadbeef" * 4, 17831, addresses=["192.168.1.20"])
    assert payload["scheme"] == "canvasforge-pair"
    assert payload["code"] == security_code_from_token(payload["token"])
    qr = pairing_qr_text(payload)
    assert qr.startswith("http://192.168.1.20:17831/?pair=")
    pasted = pasteable_pairing_code(payload)
    parsed = parse_pairing_link(pasted)
    assert parsed["token"] == payload["token"]
    assert parsed["port"] == "17831"
    from_qr = parse_pairing_link(qr)
    assert from_qr["token"] == payload["token"]


def test_parse_pairing_link_rejects_empty():
    with pytest.raises(ValueError):
        parse_pairing_link("   ")


def test_qr_matrix_has_finder_patterns():
    matrix = qr_matrix("http://192.168.1.8:17831/?pair=" + ("ab" * 16))
    assert qr_has_finder_patterns(matrix)
    assert choose_version(b"short") >= 1


def test_desktop_and_mobile_grabs_share_library_folder(tmp_path):
    library = tmp_path / "Screenshots"
    mobile = save_grab_to_library(library, _png_bytes(), source="mobile")
    desktop = save_grab_to_library(library, _png_bytes(), source="desktop")
    assert mobile.parent == desktop.parent == library
    assert mobile.name.startswith("mobile_")
    assert desktop.name.startswith("desktop_")


def test_save_grab_to_library_writes_png(tmp_path):
    library = tmp_path / "Screenshots"
    dest = save_grab_to_library(library, _png_bytes(), source="mobile")
    assert dest.exists()
    assert dest.parent == library
    assert dest.suffix == ".png"
    assert dest.name.startswith("mobile_")
    assert dest.read_bytes().startswith(b"\x89PNG")


def test_save_grab_to_library_uses_hint_and_rejects_junk(tmp_path):
    dest = save_grab_to_library(
        tmp_path,
        _png_bytes(),
        source="desktop",
        filename_hint="desk grab.png",
    )
    assert dest.name.startswith("deskgrab") or dest.name.startswith("desk")
    with pytest.raises(ValueError):
        save_grab_to_library(tmp_path, b"not-an-image")
    with pytest.raises(ValueError):
        save_grab_to_library(tmp_path, b"")


def test_sniff_image_suffix_png():
    assert sniff_image_suffix(_png_bytes(), "image/png") == ".png"


def test_mutual_confirm_issues_device_token(tmp_path):
    store = PairingStore(tmp_path / "pair.json")
    service = MobileSyncService(tmp_path / "lib", store=store, port=0, desktop_name="Omarchy")
    session = service.begin_pairing()
    assert session.security_code == security_code_from_token(session.token)
    phone = service.confirm_phone(session.token, "Pixel")
    assert phone["state"] == "phone_confirmed"
    assert store.devices() == []
    desktop = service.confirm_desktop()
    assert desktop["state"] == "paired"
    devices = store.devices()
    assert len(devices) == 1
    assert devices[0]["name"] == "Pixel"
    assert store.find_token(devices[0]["token"]) is not None
    service.stop()


def test_wrong_token_does_not_pair(tmp_path):
    service = MobileSyncService(tmp_path / "lib", store=PairingStore(tmp_path / "p.json"), port=0)
    service.begin_pairing()
    with pytest.raises(ValueError):
        service.confirm_phone("0" * 32)
    service.stop()


def test_http_pair_and_upload_to_shared_library(tmp_path):
    library = tmp_path / "Screenshots"
    store = PairingStore(tmp_path / "pair.json")
    saved = []
    service = MobileSyncService(
        library,
        store=store,
        port=0,
        on_grab_saved=saved.append,
    )
    session = service.begin_pairing()
    port = service.bound_port
    assert port
    base = f"http://127.0.0.1:{port}"

    offer = json.loads(urlopen(f"{base}/api/pair/offer?token={session.token}", timeout=2).read())
    assert offer["security_code"] == session.security_code

    confirm_req = Request(
        f"{base}/api/pair/confirm",
        data=json.dumps({"token": session.token, "name": "TestPhone"}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    phone = json.loads(urlopen(confirm_req, timeout=2).read())
    assert phone["state"] == "phone_confirmed"

    service.confirm_desktop()
    status = json.loads(urlopen(f"{base}/api/pair/status?token={session.token}", timeout=2).read())
    assert status["state"] == "paired"
    device_token = status["device_token"]

    png = _png_bytes()
    upload = Request(
        f"{base}/api/upload",
        data=png,
        headers={
            "Authorization": f"Bearer {device_token}",
            "Content-Type": "image/png",
            "X-Filename": "phone-grab.png",
        },
        method="POST",
    )
    result = json.loads(urlopen(upload, timeout=2).read())
    assert result["ok"] is True
    dest = Path(result["path"])
    assert dest.exists()
    assert dest.parent == library
    assert dest.read_bytes() == png
    assert saved == [dest]

    bad = Request(
        f"{base}/api/upload",
        data=png,
        headers={"Authorization": "Bearer not-a-real-token", "Content-Type": "image/png"},
        method="POST",
    )
    with pytest.raises(HTTPError) as err:
        urlopen(bad, timeout=2)
    assert err.value.code == 403
    service.stop()


def test_upload_rejected_before_pair(tmp_path):
    service = MobileSyncService(tmp_path / "lib", store=PairingStore(tmp_path / "p.json"), port=0)
    service.start()
    port = service.bound_port
    req = Request(
        f"http://127.0.0.1:{port}/api/upload",
        data=_png_bytes(),
        headers={"Authorization": "Bearer nope", "Content-Type": "image/png"},
        method="POST",
    )
    with pytest.raises(HTTPError) as err:
        urlopen(req, timeout=2)
    assert err.value.code == 403
    service.stop()


def test_companion_page_is_served(tmp_path):
    service = MobileSyncService(tmp_path / "lib", store=PairingStore(tmp_path / "p.json"), port=0)
    service.start()
    html = urlopen(f"http://127.0.0.1:{service.bound_port}/", timeout=2).read().decode()
    assert "Pair with desktop" in html
    assert "security code" in html
    service.stop()


def test_default_port_is_stable():
    assert DEFAULT_PORT == 17831


def test_preferences_has_mobile_pair_tab(qapp, tmp_path):
    store = PairingStore(tmp_path / "pair.json")
    service = MobileSyncService(tmp_path / "lib", store=store, port=0)
    settings = QSettings()
    dialog = PreferencesDialog(
        settings=settings,
        current_library_dir=tmp_path / "lib",
        mobile_sync=service,
    )
    titles = [dialog.tab_widget.tabText(i) for i in range(dialog.tab_widget.count())]
    assert "Mobile" in titles
    assert dialog.mobile_pair_btn.text() == "Pair Mobile Device"
    hints = [
        widget.text()
        for widget in dialog.findChildren(QLabel)
        if "Scan this QR code with the CanvasForge mobile app to securely pair" in widget.text()
    ]
    assert hints
    service.stop()
    dialog.close()
