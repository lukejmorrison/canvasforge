# Mobile pairing and shared grabs

The phone app is **canvasForge**, the same name as the desktop app. It is a **Flutter** project under [`mobile/app`](../mobile/app). iOS and Android share one Dart codebase. The PyQt6 desktop editor stays the desktop editor.

Pairing matches Buzz: scan the QR from **Settings → Mobile → Pair Mobile Device**, confirm the short security code on both sides, then send screen grabs into the desktop Image Library over LAN or Tailscale. No CanvasForge account.

Related issues: [#29](https://github.com/lukejmorrison/canvasforge/issues/29) Flutter companion, [#30](https://github.com/lukejmorrison/canvasforge/issues/30) QR pair, [#31](https://github.com/lukejmorrison/canvasforge/issues/31) LAN sync.

## What you get

- Desktop still captures and annotates locally (arrows, text, highlight, blur).
- **Export Canvas** in the Image Library writes the annotated grab into the shared folder.
- The Flutter app pairs, then uploads a screenshot to that same folder.
- The library watcher shows the new file. Open it and use **Send to Agent** as usual.

A static page under `mobile/` is still served by the desktop as a fallback if the Flutter app is not installed. The Flutter app is the product.

## Omarchy / Linux desktop

1. Quit any running CanvasForge window.
2. `bash scripts/install_canvasforge.sh --local`
3. Launch `~/.local/bin/canvasforge` (not `python main.py`, not AUR `/usr/bin/canvasforge`).
4. Set the Image Library folder if needed (`~/Pictures/Screenshots`).
5. **Edit → Preferences → Mobile → Pair Mobile Device**.

The desktop listens on port `17831` on all interfaces. After a device is paired, the listener starts with the app.

## macOS desktop

On a Mac (Intel Mini or otherwise):

```bash
bash scripts/build_macos_app.sh
open dist/CanvasForge.app
```

Then **CanvasForge → Settings → Mobile → Pair Mobile Device**. The same LAN listener and Image Library path apply.

## Flutter phone app (iOS and Android)

```bash
cd mobile/app
flutter pub get
flutter test
flutter run                 # choose the iPhone, simulator, or Android device
flutter run -d ios
flutter run -d android
```

Or `bash scripts/build_flutter_mobile.sh` (runs tests; pass `ios`, `ios-simulator`, or `apk` to build).

1. Tap **Scan desktop QR code**, or paste the `host:port#token` code.
2. Confirm the security code matches the desktop, then confirm on the desktop too.
3. Choose a screenshot or take a photo. It appears in the Image Library.

### iOS signing

`flutter build ios --simulator --no-codesign` and `flutter build ios --no-codesign` work on a Mac with Xcode and do not need an App Store certificate.

A device-installable signed IPA / TestFlight build needs a Team in Xcode (**Signing & Capabilities** on `ios/Runner.xcworkspace`). Cloud agents cannot do that. Bundle id: `com.lukejmorrison.canvasforgeMobile`.

### Android

`flutter build apk` produces a sideloadable APK. Play Store is later.

## Send to Agent

Unchanged. Open the shared grab from the Image Library, annotate if you want, then **Send to Agent** (`Ctrl+Shift+A`).

## Unpair

**Preferences → Mobile** lists paired phones. In the Flutter app, tap **Forget this desktop**.
