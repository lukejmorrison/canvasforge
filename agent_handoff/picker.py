"""Send to Agent chooser dialog."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from agent_handoff.models import AgentTarget


class AgentPickerDialog(QDialog):
    """List discovered agents and return the chosen target."""

    def __init__(self, targets: list[AgentTarget], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Send to Agent")
        self.setMinimumWidth(460)
        self.setMinimumHeight(360)
        self._targets = list(targets)
        self._chosen: AgentTarget | None = None
        self._pin_id = ""
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        hint = QLabel(
            "Choose a local agent. Offline rows stay visible but cannot be sent to."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        buttons = QHBoxLayout()
        self.pin_button = QPushButton("Pin as default")
        self.pin_button.clicked.connect(self._pin_selected)
        buttons.addWidget(self.pin_button)
        buttons.addStretch()
        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Send")
        box.accepted.connect(self._accept_current)
        box.rejected.connect(self.reject)
        self.send_button = box.button(QDialogButtonBox.StandardButton.Ok)
        buttons.addWidget(box)
        layout.addLayout(buttons)

        for target in self._targets:
            item = QListWidgetItem(self._row_text(target))
            item.setData(Qt.ItemDataRole.UserRole, target.id)
            if not target.can_send:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.list_widget.addItem(item)

        self.list_widget.itemDoubleClicked.connect(self._accept_item)
        self.list_widget.itemSelectionChanged.connect(self._sync_buttons)
        if self.list_widget.count():
            for index in range(self.list_widget.count()):
                item = self.list_widget.item(index)
                if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                    self.list_widget.setCurrentRow(index)
                    break
        self._sync_buttons()

    def _row_text(self, target: AgentTarget) -> str:
        marks = []
        if target.pinned:
            marks.append("pinned")
        if target.last_used:
            marks.append("last used")
        suffix = f" · {', '.join(marks)}" if marks else ""
        return f"{target.name}  —  {target.kind} · {target.status_label()}{suffix}"

    def _selected_target(self) -> AgentTarget | None:
        item = self.list_widget.currentItem()
        if item is None:
            return None
        target_id = item.data(Qt.ItemDataRole.UserRole)
        for target in self._targets:
            if target.id == target_id:
                return target
        return None

    def _sync_buttons(self) -> None:
        if not hasattr(self, "send_button"):
            return
        target = self._selected_target()
        enabled = bool(target and target.can_send)
        self.send_button.setEnabled(enabled)
        self.pin_button.setEnabled(target is not None)

    def _pin_selected(self) -> None:
        target = self._selected_target()
        if target is None:
            return
        self._pin_id = target.id

    def _accept_item(self, item: QListWidgetItem) -> None:
        target_id = item.data(Qt.ItemDataRole.UserRole)
        for target in self._targets:
            if target.id == target_id and target.can_send:
                self._chosen = target
                self.accept()
                return

    def _accept_current(self) -> None:
        target = self._selected_target()
        if target is None or not target.can_send:
            return
        self._chosen = target
        self.accept()

    def chosen_target(self) -> AgentTarget | None:
        return self._chosen

    def pin_id(self) -> str:
        return self._pin_id
