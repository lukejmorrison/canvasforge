import os
import sys
from pathlib import Path

import pytest

import main


def _reset_guard():
    main._macos_secure_restorable_installed = False


def test_guard_is_noop_off_darwin(monkeypatch):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    _reset_guard()
    assert main.install_macos_secure_restorable_state(platform="linux") is False
    assert "NSQuitAlwaysKeepsWindows" not in os.environ
    assert main._macos_secure_restorable_installed is False


def test_guard_disables_restore_when_objc_missing(monkeypatch):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    monkeypatch.setattr(main, "_install_cocoa_secure_restorable_delegate", lambda: False)
    _reset_guard()
    assert main.install_macos_secure_restorable_state(platform="darwin") is False
    assert os.environ["NSQuitAlwaysKeepsWindows"] == "NO"


def test_guard_survives_objc_exception(monkeypatch):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)

    def _boom():
        raise RuntimeError("objc unavailable")

    monkeypatch.setattr(main, "_install_cocoa_secure_restorable_delegate", _boom)
    _reset_guard()
    assert main.install_macos_secure_restorable_state(platform="darwin") is False
    assert os.environ["NSQuitAlwaysKeepsWindows"] == "NO"


def test_guard_installs_delegate_on_darwin(monkeypatch):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    monkeypatch.setattr(main, "_install_cocoa_secure_restorable_delegate", lambda: True)
    _reset_guard()
    assert main.install_macos_secure_restorable_state(platform="darwin") is True
    assert os.environ["NSQuitAlwaysKeepsWindows"] == "NO"
    assert main._macos_secure_restorable_installed is True
    # Second call is idempotent and does not re-enter objc.
    calls = {"n": 0}

    def _should_not_run():
        calls["n"] += 1
        return False

    monkeypatch.setattr(main, "_install_cocoa_secure_restorable_delegate", _should_not_run)
    assert main.install_macos_secure_restorable_state(platform="darwin") is True
    assert calls["n"] == 0


def test_real_objc_installer_is_safe_without_appkit(monkeypatch):
    """Linux has no AppKit; the ctypes path must return False, not raise."""
    if sys.platform == "darwin":
        pytest.skip("real AppKit path is exercised on the Mac Mini, not here")
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    _reset_guard()
    assert main.install_macos_secure_restorable_state(platform="darwin") is False
    assert os.environ["NSQuitAlwaysKeepsWindows"] == "NO"


def test_startup_establishes_guard_before_qapplication():
    """Monterey aborts if the Cocoa delegate is attached after QApplication()."""
    source = Path(main.__file__).read_text(encoding="utf-8")
    main_block = source.split('if __name__ == "__main__":', 1)[1]
    guard_at = main_block.find("install_macos_secure_restorable_state(")
    qapp_at = main_block.find("QApplication(sys.argv)")
    assert guard_at != -1
    assert qapp_at != -1
    assert guard_at < qapp_at


def test_delegate_selectors_opt_in_and_ignore_saved_state():
    assert main._MACOS_SECURE_RESTORABLE_SELECTOR == b"applicationSupportsSecureRestorableState:"
    assert main._MACOS_SHOULD_RESTORE_SELECTOR == b"applicationShouldRestoreApplicationState:"
    assert main._MACOS_SHOULD_SAVE_SELECTOR == b"applicationShouldSaveApplicationState:"
