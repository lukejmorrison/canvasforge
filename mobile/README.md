# CanvasForge mobile companion

This folder is the **capture puck** for phones. It is not a rewrite of the PyQt6 desktop editor and not a hosted website.

The desktop app serves these files on your LAN (or Tailscale) after you open **Settings → Mobile → Pair Mobile Device**. iOS Safari and Android Chrome can scan the QR code, confirm the short security code, and send screenshots into the same Image Library folder the desktop already watches.

## Pair and send a grab

1. On Omarchy, launch the installed desktop app (`canvasforge` / `~/.local/bin/canvasforge`).
2. Open **Edit → Preferences → Mobile** (or **Settings → Mobile**).
3. Click **Pair Mobile Device**.
4. On the phone, scan the QR code — or type the `host:port#token` code.
5. Confirm the same security code on both devices.
6. Choose a screenshot or photo on the phone. It appears in the desktop Image Library.
7. On the desktop, open the grab and use **Send to Agent**.

After pairing, the phone keeps the desktop address and device token. You do not need to scan again, and there is no CanvasForge cloud account.

## Flutter / App Store

A Flutter APK and TestFlight IPA are later roadmap items ([#29](https://github.com/lukejmorrison/canvasforge/issues/29), [#32](https://github.com/lukejmorrison/canvasforge/issues/32), [#33](https://github.com/lukejmorrison/canvasforge/issues/33)). This LAN companion is the smallest path that works on iOS and Android today. The HTTP API (`/api/pair/*`, `/api/upload`) is what a later native app should call.

## Manual upload (no phone)

From another machine on the same network, after pairing:

```bash
curl -H "Authorization: Bearer DEVICE_TOKEN" \
  -H "Content-Type: image/png" \
  --data-binary @grab.png \
  http://DESKTOP_IP:17831/api/upload
```
