"""Local mobile pairing and grab sync for CanvasForge.

Desktop listens on the LAN (or Tailscale). A phone scans a QR code, both sides
confirm a short security code, then the phone POSTs screenshots into the Image
Library folder. No hosted account and no public relay.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from mobile_qr import qr_matrix

PAIR_SCHEME = "canvasforge-pair"
DEFAULT_PORT = 17831
PAIRING_TTL_SEC = 10 * 60
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_UPLOAD_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
GIF_MAGIC = b"GIF8"
WEBP_RIFF = b"RIFF"
STORE_FILENAME = "mobile_pairing.json"

# Crockford base32 without I, L, O, U — easy to read aloud.
_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def app_data_dir() -> Path:
    xdg_data = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data) if xdg_data else Path.home() / ".local" / "share"
    path = base / "canvasforge"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_store_path() -> Path:
    return app_data_dir() / STORE_FILENAME


def resource_root() -> Path:
    """Checkout directory, or PyInstaller extract dir inside CanvasForge.app."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
    return Path(__file__).resolve().parent


def companion_dir() -> Path:
    return resource_root() / "mobile"


def security_code_from_token(token: str) -> str:
    """Short SAS both devices show. Derived from the pairing token."""
    digest = hmac.new(b"canvasforge-pair-sas", token.encode("ascii"), "sha256").digest()
    chars = [_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in digest[:8]]
    return f"{''.join(chars[:4])}-{''.join(chars[4:])}"


def new_pairing_token() -> str:
    return secrets.token_hex(16)


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def constant_time_equals(left: str, right: str) -> bool:
    if not isinstance(left, str) or not isinstance(right, str):
        return False
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def lan_addresses() -> List[str]:
    """IPv4 addresses other devices on LAN/Tailscale can reach."""
    found: List[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127.") or ip.startswith("0."):
            return
        if ip not in found:
            found.append(ip)

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET, socket.SOCK_STREAM):
            add(info[4][0])
    except OSError:
        pass
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("1.1.1.1", 80))
        add(sock.getsockname()[0])
        sock.close()
    except OSError:
        pass
    return found


def pairing_urls(port: int, addresses: Optional[List[str]] = None) -> List[str]:
    hosts = addresses if addresses is not None else lan_addresses()
    if not hosts:
        hosts = ["127.0.0.1"]
    return [f"http://{host}:{int(port)}" for host in hosts]


def build_pairing_payload(
    token: str,
    port: int,
    *,
    desktop_name: str = "CanvasForge",
    addresses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    urls = pairing_urls(port, addresses)
    code = security_code_from_token(token)
    return {
        "v": 1,
        "scheme": PAIR_SCHEME,
        "name": desktop_name,
        "urls": urls,
        "token": token,
        "code": code,
        "port": int(port),
    }


def pairing_qr_text(payload: Dict[str, Any]) -> str:
    """Compact QR body. Phone opens the first URL with the pairing token."""
    urls = payload.get("urls") or []
    url = urls[0] if urls else f"http://127.0.0.1:{payload.get('port', DEFAULT_PORT)}"
    token = payload["token"]
    return f"{url}/?pair={token}"


def parse_pairing_link(text: str) -> Dict[str, str]:
    """Accept a scanned QR URL or a pasted ``host:port#token`` code."""
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Pairing code is empty")
    if raw.startswith("http://") or raw.startswith("https://"):
        parsed = urlparse(raw)
        query = parse_qs(parsed.query)
        token = (query.get("pair") or [""])[0]
        if not token:
            raise ValueError("Pairing link is missing the pair token")
        base = f"{parsed.scheme}://{parsed.netloc}"
        return {"url": base, "token": token, "host": parsed.hostname or "", "port": str(parsed.port or "")}
    if "#" in raw:
        hostport, token = raw.split("#", 1)
        hostport = hostport.strip()
        token = token.strip()
        if ":" in hostport:
            host, port = hostport.rsplit(":", 1)
        else:
            host, port = hostport, str(DEFAULT_PORT)
        return {
            "url": f"http://{host}:{port}",
            "token": token,
            "host": host,
            "port": port,
        }
    raise ValueError("Paste a pairing link or host:port#token")


def pasteable_pairing_code(payload: Dict[str, Any]) -> str:
    urls = payload.get("urls") or []
    parsed = urlparse(urls[0]) if urls else urlparse(f"http://127.0.0.1:{payload.get('port', DEFAULT_PORT)}")
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or payload.get("port", DEFAULT_PORT)
    return f"{host}:{port}#{payload['token']}"


def sniff_image_suffix(data: bytes, content_type: str = "") -> str:
    ctype = (content_type or "").split(";")[0].strip().lower()
    if data.startswith(PNG_MAGIC):
        return ".png"
    if data.startswith(JPEG_MAGIC):
        return ".jpg"
    if data.startswith(GIF_MAGIC):
        return ".gif"
    if data.startswith(WEBP_RIFF) and b"WEBP" in data[:16]:
        return ".webp"
    if ctype in ALLOWED_UPLOAD_TYPES:
        return ALLOWED_UPLOAD_TYPES[ctype]
    raise ValueError("Only PNG, JPEG, WebP, or GIF grabs can be synced")


def next_grab_path(library_dir: Path, source: str = "mobile") -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_source = "".join(ch for ch in source if ch.isalnum() or ch in ("-", "_")) or "grab"
    base = f"{safe_source}_{stamp}"
    candidate = library_dir / f"{base}.png"
    counter = 1
    while candidate.exists():
        candidate = library_dir / f"{base}_{counter}.png"
        counter += 1
    return candidate


def save_grab_to_library(
    library_dir: Path,
    image_bytes: bytes,
    *,
    source: str = "mobile",
    content_type: str = "",
    filename_hint: str = "",
) -> Path:
    """Write a capture into the Image Library folder and return the path."""
    if not image_bytes:
        raise ValueError("Grab is empty")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise ValueError("Grab is larger than 25 MB")
    suffix = sniff_image_suffix(image_bytes, content_type)
    library_dir = Path(library_dir).expanduser()
    library_dir.mkdir(parents=True, exist_ok=True)
    if filename_hint:
        stem = Path(filename_hint).stem
        safe = "".join(ch for ch in stem if ch.isalnum() or ch in ("-", "_", "."))[:80]
        dest = library_dir / f"{safe}{suffix}"
        counter = 1
        while dest.exists():
            dest = library_dir / f"{safe}_{counter}{suffix}"
            counter += 1
    else:
        dest = next_grab_path(library_dir, source).with_suffix(suffix)
    dest.write_bytes(image_bytes)
    return dest


class PairingStore:
    """JSON file of paired phones. Tokens never go in logs."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else default_store_path()
        self._lock = threading.Lock()
        self._data: Dict[str, Any] = {"devices": []}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            self._data = {"devices": []}
            return
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {"devices": []}
        devices = loaded.get("devices") if isinstance(loaded, dict) else []
        self._data = {"devices": list(devices) if isinstance(devices, list) else []}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def devices(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._data["devices"]]

    def add_device(self, name: str, device_token: str) -> Dict[str, Any]:
        record = {
            "id": secrets.token_hex(8),
            "name": name or "CanvasForge phone",
            "token": device_token,
            "paired_at": int(time.time()),
        }
        with self._lock:
            self._data["devices"].append(record)
            self.save()
        return dict(record)

    def remove_device(self, device_id: str) -> bool:
        with self._lock:
            before = len(self._data["devices"])
            self._data["devices"] = [
                item for item in self._data["devices"] if item.get("id") != device_id
            ]
            if len(self._data["devices"]) == before:
                return False
            self.save()
            return True

    def find_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token:
            return None
        with self._lock:
            for item in self._data["devices"]:
                if constant_time_equals(str(item.get("token") or ""), token):
                    return dict(item)
        return None


class PairingSession:
    def __init__(self, token: str, port: int, desktop_name: str, addresses: List[str]) -> None:
        self.token = token
        self.port = port
        self.desktop_name = desktop_name
        self.addresses = addresses
        self.security_code = security_code_from_token(token)
        self.created_at = time.time()
        self.expires_at = self.created_at + PAIRING_TTL_SEC
        self.phone_confirmed = False
        self.desktop_confirmed = False
        self.device_token: Optional[str] = None
        self.device: Optional[Dict[str, Any]] = None
        self.phone_name = "CanvasForge phone"

    def expired(self) -> bool:
        return time.time() > self.expires_at

    def payload(self) -> Dict[str, Any]:
        return build_pairing_payload(
            self.token,
            self.port,
            desktop_name=self.desktop_name,
            addresses=self.addresses,
        )

    def public_offer(self) -> Dict[str, Any]:
        return {
            "state": self.state(),
            "name": self.desktop_name,
            "security_code": self.security_code,
            "expires_at": int(self.expires_at),
        }

    def state(self) -> str:
        if self.device_token:
            return "paired"
        if self.expired():
            return "expired"
        if self.phone_confirmed and self.desktop_confirmed:
            return "confirming"
        if self.phone_confirmed:
            return "phone_confirmed"
        if self.desktop_confirmed:
            return "desktop_confirmed"
        return "waiting"

    def complete(self, store: PairingStore) -> Dict[str, Any]:
        if self.device_token and self.device:
            return self.device
        self.device_token = new_device_token()
        self.device = store.add_device(self.phone_name, self.device_token)
        return self.device


class MobileSyncService:
    """Pairing state plus the LAN HTTP listener."""

    def __init__(
        self,
        library_dir: Path,
        *,
        store: Optional[PairingStore] = None,
        port: int = DEFAULT_PORT,
        desktop_name: str = "CanvasForge",
        on_grab_saved: Optional[Callable[[Path], None]] = None,
    ) -> None:
        self.library_dir = Path(library_dir)
        self.store = store or PairingStore()
        self.port = int(port)
        self.desktop_name = desktop_name
        self.on_grab_saved = on_grab_saved
        self._lock = threading.Lock()
        self._session: Optional[PairingSession] = None
        self._httpd: Optional[ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._bound_port: Optional[int] = None

    @property
    def bound_port(self) -> Optional[int]:
        return self._bound_port

    def is_listening(self) -> bool:
        return self._httpd is not None

    def begin_pairing(self) -> PairingSession:
        self.ensure_listening()
        port = self._bound_port or self.port
        session = PairingSession(
            new_pairing_token(),
            port,
            self.desktop_name,
            lan_addresses(),
        )
        with self._lock:
            self._session = session
        return session

    def current_session(self) -> Optional[PairingSession]:
        with self._lock:
            session = self._session
            if session is None:
                return None
            if session.expired() and not session.device_token:
                self._session = None
                return None
            return session

    def cancel_pairing(self) -> None:
        with self._lock:
            self._session = None

    def confirm_desktop(self) -> Dict[str, Any]:
        with self._lock:
            session = self._session
            if session is None or session.expired():
                raise ValueError("No active pairing session")
            session.desktop_confirmed = True
            if session.phone_confirmed:
                device = session.complete(self.store)
                return {"state": "paired", "device": device, "security_code": session.security_code}
            return {"state": session.state(), "security_code": session.security_code}

    def confirm_phone(self, token: str, phone_name: str = "") -> Dict[str, Any]:
        with self._lock:
            session = self._session
            if session is None or session.expired():
                raise ValueError("No active pairing session")
            if not constant_time_equals(session.token, token):
                raise ValueError("Pairing token does not match")
            if phone_name:
                session.phone_name = phone_name
            session.phone_confirmed = True
            if session.desktop_confirmed:
                device = session.complete(self.store)
                return {
                    "state": "paired",
                    "device_token": session.device_token,
                    "security_code": session.security_code,
                    "device": device,
                }
            return {"state": session.state(), "security_code": session.security_code}

    def pairing_status(self, token: str) -> Dict[str, Any]:
        with self._lock:
            session = self._session
            if session is None:
                return {"state": "idle"}
            if not constant_time_equals(session.token, token):
                raise ValueError("Pairing token does not match")
            status = session.public_offer()
            if session.device_token:
                status["device_token"] = session.device_token
                status["urls"] = pairing_urls(session.port, session.addresses)
            return status

    def ingest_grab(
        self,
        image_bytes: bytes,
        *,
        device_token: str,
        content_type: str = "",
        filename_hint: str = "",
    ) -> Path:
        device = self.store.find_token(device_token)
        if device is None:
            raise PermissionError("Phone is not paired")
        path = save_grab_to_library(
            self.library_dir,
            image_bytes,
            source="mobile",
            content_type=content_type,
            filename_hint=filename_hint,
        )
        if self.on_grab_saved is not None:
            self.on_grab_saved(path)
        return path

    def set_library_dir(self, library_dir: Path) -> None:
        self.library_dir = Path(library_dir)

    def ensure_listening(self) -> int:
        if self._httpd is not None and self._bound_port:
            return self._bound_port
        self.start()
        assert self._bound_port is not None
        return self._bound_port

    def start(self) -> int:
        if self._httpd is not None and self._bound_port:
            return self._bound_port
        handler = _make_handler(self)
        httpd = ThreadingHTTPServer(("0.0.0.0", int(self.port)), handler)
        httpd.daemon_threads = True
        thread = threading.Thread(target=httpd.serve_forever, name="canvasforge-mobile-sync", daemon=True)
        thread.start()
        self._httpd = httpd
        self._thread = thread
        self._bound_port = httpd.server_address[1]
        return self._bound_port

    def stop(self) -> None:
        httpd = self._httpd
        self._httpd = None
        self._bound_port = None
        if httpd is not None:
            httpd.shutdown()
            httpd.server_close()
        thread = self._thread
        self._thread = None
        if thread is not None:
            thread.join(timeout=2)


def _read_static(name: str) -> Optional[bytes]:
    path = companion_dir() / name
    if not path.is_file():
        return None
    return path.read_bytes()


def _make_handler(service: MobileSyncService):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self._cors()
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: int, payload: Dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _read_body(self) -> bytes:
            length = int(self.headers.get("Content-Length") or "0")
            if length < 0 or length > MAX_UPLOAD_BYTES + 4096:
                raise ValueError("Upload is too large")
            return self.rfile.read(length) if length else b""

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                data = _read_static("index.html")
                if data is None:
                    self._send(404, b"mobile companion missing", "text/plain")
                    return
                self._send(200, data, "text/html; charset=utf-8")
                return
            static_map = {
                "/app.js": ("app.js", "text/javascript; charset=utf-8"),
                "/style.css": ("style.css", "text/css; charset=utf-8"),
                "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
            }
            if path in static_map:
                name, ctype = static_map[path]
                data = _read_static(name)
                if data is None:
                    self._send(404, b"missing", "text/plain")
                    return
                self._send(200, data, ctype)
                return
            if path == "/icon.png":
                icon = Path(__file__).resolve().parent / "assets" / "app_icons" / "canvasForge_app_icon.png"
                if icon.is_file():
                    self._send(200, icon.read_bytes(), "image/png")
                    return
                self._send(404, b"missing", "text/plain")
                return
            if path == "/api/health":
                self._send_json(200, {"ok": True, "listening": True})
                return
            if path == "/api/pair/offer":
                query = parse_qs(parsed.query)
                token = (query.get("token") or [""])[0]
                try:
                    session = service.current_session()
                    if session is None or not constant_time_equals(session.token, token):
                        self._send_json(404, {"error": "No matching pairing session"})
                        return
                    self._send_json(200, session.public_offer())
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            if path == "/api/pair/status":
                query = parse_qs(parsed.query)
                token = (query.get("token") or [""])[0]
                try:
                    self._send_json(200, service.pairing_status(token))
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/api/pair/confirm":
                try:
                    payload = json.loads(self._read_body().decode("utf-8") or "{}")
                    token = str(payload.get("token") or "")
                    name = str(payload.get("name") or "CanvasForge phone")
                    result = service.confirm_phone(token, name)
                    self._send_json(200, result)
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                except json.JSONDecodeError:
                    self._send_json(400, {"error": "Invalid JSON"})
                return
            if parsed.path == "/api/upload":
                auth = self.headers.get("Authorization") or ""
                token = ""
                if auth.lower().startswith("bearer "):
                    token = auth[7:].strip()
                if not token:
                    query = parse_qs(parsed.query)
                    token = (query.get("token") or [""])[0]
                try:
                    body = self._read_body()
                    content_type = self.headers.get("Content-Type") or ""
                    filename = self.headers.get("X-Filename") or ""
                    path = service.ingest_grab(
                        body,
                        device_token=token,
                        content_type=content_type,
                        filename_hint=filename,
                    )
                    self._send_json(200, {"ok": True, "path": str(path), "name": path.name})
                except PermissionError as exc:
                    self._send_json(403, {"error": str(exc)})
                except ValueError as exc:
                    self._send_json(400, {"error": str(exc)})
                return
            self._send(404, b"not found", "text/plain")

    return Handler


def pairing_qr_matrix(payload: Dict[str, Any]) -> List[List[int]]:
    return qr_matrix(pairing_qr_text(payload))
