# Mobile pairing and shared grabs

CanvasForge keeps screen grabs in one Image Library folder. A phone on the same LAN (or Tailscale) can pair like Buzz and drop captures into that folder. There is no CanvasForge account and no public website in the middle.

Related issues: [#29](https://github.com/lukejmorrison/canvasforge/issues/29) companion, [#30](https://github.com/lukejmorrison/canvasforge/issues/30) QR pair, [#31](https://github.com/lukejmorrison/canvasforge/issues/31) LAN sync.

## What you get

- Desktop still captures and annotates locally (arrows, text, highlight, blur).
- **Export Canvas** in the Image Library writes the annotated grab into the shared folder.
- A phone opens the local companion served by the desktop, pairs, and uploads a screenshot to the same folder.
- The library watcher shows the new file. Open it and use **Send to Agent** as usual.

## Omarchy desktop

1. Install or refresh the daily-driver tree:

   ```bash
   bash scripts/install_canvasforge.sh --local
   ~/.local/bin/canvasforge
   ```

   Quit any already-running CanvasForge window first. Do not test with `python main.py` if you want the installed launcher.

2. Set the Image Library folder (**Edit → Preferences → Folders**, or the sidebar combo) to the folder both devices should share. Default is usually `~/Pictures/Screenshots`.

3. Open **Edit → Preferences → Mobile** (Settings → Mobile).

4. Click **Pair Mobile Device**. The desktop shows a QR code and a short security code.

5. Leave Preferences open until both sides have confirmed.

The desktop listens on port `17831` on all interfaces so a phone on LAN or Tailscale can reach it. After a device is paired, the listener starts with the app so you do not pair again.

## Phone (iOS or Android)

The companion is the page the desktop serves at `http://DESKTOP_IP:17831/`. Scan the QR code, or paste the `host:port#token` code.

1. Confirm the security code matches the desktop, then tap **Confirm pairing**.
2. Confirm on the desktop too.
3. Choose a screenshot or take a photo. It appears in the Image Library.
4. Optional: Add the page to the Home Screen. It still talks only to your desktop.

iOS cannot share the system screen-recording buffer into a browser the way Android Chrome sometimes can. Take a screenshot, then pick it from Photos.

## Send to Agent

Unchanged. Open the shared grab from the Image Library, annotate if you want, then **Send to Agent** (`Ctrl+Shift+A`). Clipboard / folder / command targets stay under **Preferences → Agent**.

## Unpair

**Preferences → Mobile** lists paired phones. Remove one there. On the phone, tap **Forget this desktop**.

## Later native apps

`/api/pair/offer`, `/api/pair/confirm`, `/api/pair/status`, and `/api/upload` are the protocol a Flutter APK can call. See [`mobile/README.md`](../mobile/README.md).
