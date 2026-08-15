# CanvasForge mobile app

This Flutter project **is** the CanvasForge phone app. The same Dart code ships on iOS and Android. It is a capture companion, not a rewrite of the PyQt6 desktop editor.

Pairing matches Buzz: scan the QR code from desktop **Settings → Mobile → Pair Mobile Device**, confirm the short security code on both sides, then send screen grabs into the desktop Image Library over LAN or Tailscale. No CanvasForge account.

## Run (same project, both phones)

From a Mac with Xcode (iOS) and/or Android Studio / an Android SDK:

```bash
cd mobile/app
flutter pub get
flutter test
flutter run                    # pick the attached iPhone, simulator, or Android device
flutter run -d ios
flutter run -d android
```

Pair with a running desktop build on the same LAN or Tailscale, then send a screenshot.

## Pair with the desktop

1. On the desktop (Omarchy or the macOS `.app`), open **Edit → Preferences → Mobile → Pair Mobile Device**.
2. In this app, tap **Scan desktop QR code**, or paste the `host:port#token` code.
3. Confirm the security code matches on both devices.
4. Choose a screenshot or take a photo. It appears in the desktop Image Library.
5. On the desktop, open the grab and use **Send to Agent**.

After pairing, the phone keeps the desktop address and device token. You do not scan again.

## iOS (Xcode)

On a Mac:

```bash
cd mobile/app
flutter pub get
open ios/Runner.xcworkspace
```

Or from the CLI:

```bash
flutter build ios --simulator --no-codesign
flutter build ios --no-codesign
```

Those commands exist only on macOS. A Linux host has no `flutter build ios` subcommand. On Linux, `flutter test` and `flutter build bundle` compile the same Dart; they do not produce `Runner.app`.

A signed IPA / TestFlight upload needs a development team in Xcode (**Signing & Capabilities**). This cloud environment cannot sign an App Store IPA. Bundle id: `com.lukejmorrison.canvasforgeMobile`.

The app uses cleartext HTTP to the desktop on LAN/Tailscale (`NSAllowsLocalNetworking` plus `NSAllowsArbitraryLoads`). That is intentional; there is no public host.

## Android

```bash
cd mobile/app
flutter build apk
# or
flutter run -d android
```

Sideload the APK. Play Store packaging is later.

## Desktop (macOS) — separate from this app

The phone app does not replace the desktop editor. On a Mac Mini, build the PyQt6 app with:

```bash
bash scripts/build_macos_app.sh
open dist/CanvasForge.app
```

That script must run on macOS. See [docs/mobile-pairing.md](../../docs/mobile-pairing.md).

## Protocol

`/api/pair/offer`, `/api/pair/confirm`, `/api/pair/status`, `/api/upload` — same LAN listener the desktop already runs. Dart client: `lib/pairing.dart`, `lib/sync_client.dart`.
