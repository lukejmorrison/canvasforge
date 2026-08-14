import os
import sys
from pathlib import Path

import pytest

import macos_restorable
import main


BUNDLE_ID = macos_restorable.BUNDLE_ID


def _poison_saved_state(home: Path) -> Path:
    path = (
        home / "Library" / "Saved Application State" / f"{BUNDLE_ID}.savedState"
    )
    path.mkdir(parents=True)
    (path / "windows.plist").write_text("poison", encoding="utf-8")
    return path


def test_guard_is_noop_off_darwin(monkeypatch, tmp_path):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    poison = _poison_saved_state(tmp_path)
    assert macos_restorable.install_macos_secure_restorable_state(
        platform="linux", home=tmp_path
    ) is False
    assert "NSQuitAlwaysKeepsWindows" not in os.environ
    assert poison.exists()


def test_install_deletes_leftover_saved_state(monkeypatch, tmp_path):
    monkeypatch.delenv("NSQuitAlwaysKeepsWindows", raising=False)
    poison = _poison_saved_state(tmp_path)
    assert macos_restorable.install_macos_secure_restorable_state(
        platform="darwin", home=tmp_path
    ) is True
    assert os.environ["NSQuitAlwaysKeepsWindows"] == "NO"
    assert os.environ["ApplePersistenceIgnoreState"] == "YES"
    assert not poison.exists()


def test_discard_only_removes_this_bundle(tmp_path):
    ours = _poison_saved_state(tmp_path)
    other = (
        tmp_path / "Library" / "Saved Application State" / "com.example.Other.savedState"
    )
    other.mkdir(parents=True)
    (other / "windows.plist").write_text("keep", encoding="utf-8")
    removed = macos_restorable.discard_macos_saved_application_state(
        platform="darwin", home=tmp_path
    )
    assert ours in removed
    assert not ours.exists()
    assert other.exists()


def test_linux_does_not_touch_real_home(monkeypatch, tmp_path):
    monkeypatch.setattr(macos_restorable, "is_darwin", lambda platform=None: False)
    poison = _poison_saved_state(tmp_path)
    assert macos_restorable.discard_macos_saved_application_state(
        platform="linux", home=tmp_path
    ) == []
    assert poison.exists()


def test_persistent_ui_disable_is_safe_without_appkit():
    if sys.platform == "darwin":
        pytest.skip("real AppKit path is exercised on the Mac Mini, not here")
    macos_restorable._persistent_ui_disabled = False
    assert macos_restorable.disable_macos_persistent_ui(platform="linux") is False
    assert macos_restorable.disable_macos_persistent_ui(platform="darwin") is False


def test_startup_discards_state_before_qapplication():
    source = Path(main.__file__).read_text(encoding="utf-8")
    main_block = source.split('if __name__ == "__main__":', 1)[1]
    discard_at = main_block.find("install_macos_secure_restorable_state(")
    qapp_at = main_block.find("QApplication(sys.argv)")
    persistent_at = main_block.find("disable_macos_persistent_ui(")
    assert discard_at != -1
    assert qapp_at != -1
    assert persistent_at != -1
    assert discard_at < qapp_at < persistent_at


def test_startup_does_not_create_nsapplication_before_qapplication():
    """sharedApplication-then-YES-delegate is the Monterey ASI."""
    source = Path(main.__file__).read_text(encoding="utf-8")
    main_block = source.split('if __name__ == "__main__":', 1)[1]
    before_qapp = main_block.split("QApplication(sys.argv)", 1)[0]
    assert "sharedApplication" not in before_qapp
    assert "setDelegate" not in before_qapp


def test_spec_disables_argv_emulation_and_registers_rthook():
    spec = Path(main.__file__).with_name("canvasforge.spec").read_text(encoding="utf-8")
    assert "argv_emulation=False" in spec
    assert "pyi_rth_disable_savedstate.py" in spec
    assert "macos_restorable" in spec
