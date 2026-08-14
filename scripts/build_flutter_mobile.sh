#!/usr/bin/env bash
# Build the CanvasForge Flutter companion (iOS / Android).
# iOS device/simulator binaries require macOS + Xcode.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP="$ROOT/mobile/app"

if ! command -v flutter >/dev/null 2>&1; then
  echo "flutter is not on PATH. Install Flutter, then:"
  echo "  cd mobile/app && flutter pub get && flutter test && flutter run"
  exit 1
fi

cd "$APP"
flutter pub get
flutter test
flutter analyze --no-fatal-infos

TARGET="${1:-}"
case "$TARGET" in
  ios-simulator)
    if [[ "$(uname -s)" != "Darwin" ]]; then
      echo "iOS simulator builds must run on a Mac with Xcode."
      echo "On a Mac: flutter build ios --simulator --no-codesign"
      exit 1
    fi
    flutter build ios --simulator --no-codesign
    echo "Simulator app: $APP/build/ios/iphonesimulator/Runner.app"
    ;;
  ios)
    if [[ "$(uname -s)" != "Darwin" ]]; then
      echo "iOS device builds must run on a Mac with Xcode."
      echo "On a Mac: flutter build ios --no-codesign"
      echo "Signed IPA: open ios/Runner.xcworkspace, set a Team, Product → Archive."
      exit 1
    fi
    flutter build ios --no-codesign
    echo "Unsigned iOS build is under $APP/build/ios"
    echo "For a signed IPA, open ios/Runner.xcworkspace and archive in Xcode."
    ;;
  apk|android)
    flutter build apk
    echo "APK: $APP/build/app/outputs/flutter-apk/app-release.apk"
    ;;
  ""|test)
    echo "Tests and analyze passed. Next:"
    echo "  flutter run -d ios"
    echo "  flutter run -d android"
    echo "  $0 ios-simulator   # Mac + Xcode"
    echo "  $0 apk"
    ;;
  *)
    echo "Usage: $0 [test|ios|ios-simulator|apk]"
    exit 1
    ;;
esac
