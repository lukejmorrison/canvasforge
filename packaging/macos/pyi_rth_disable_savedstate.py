# PyInstaller runtime hook: runs before main.py (and before Qt is useful).
# Discard leftover AppKit savedState so the windowed bootloader / libqcocoa
# cannot initialize NSPersistentUI from a poisoned directory.
from macos_restorable import install_macos_secure_restorable_state

install_macos_secure_restorable_state()
