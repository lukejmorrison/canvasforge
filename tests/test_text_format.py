from PyQt6.QtGui import QColor, QFont, QTextCursor
from PyQt6.QtWidgets import QGraphicsScene

from main import CanvasTextItem


def _fmt_at(item, position=0):
    cursor = QTextCursor(item.document())
    cursor.setPosition(int(position))
    return cursor.charFormat()


def test_bold_then_italic_combines(qapp):
    item = CanvasTextItem("hello")
    item.apply_char_format(bold=True)
    item.apply_char_format(italic=True)
    fmt = _fmt_at(item)
    assert fmt.fontWeight() == QFont.Weight.Bold
    assert fmt.fontItalic() is True


def test_colour_does_not_clear_underline(qapp):
    item = CanvasTextItem("hello")
    item.apply_char_format(underline=True)
    item.apply_char_format(color=QColor("#cc0000"))
    fmt = _fmt_at(item)
    assert fmt.fontUnderline() is True
    assert QColor(fmt.foreground().color()).name() == "#cc0000"


def test_underline_then_bold_keeps_both(qapp):
    item = CanvasTextItem("hello")
    item.apply_char_format(underline=True)
    item.apply_char_format(bold=True)
    fmt = _fmt_at(item)
    assert fmt.fontUnderline() is True
    assert fmt.fontWeight() == QFont.Weight.Bold


def test_box_scope_recolours_whole_document(qapp):
    item = CanvasTextItem("hello world")
    item.apply_char_format(color=QColor("#336699"))
    assert QColor(_fmt_at(item, 0).foreground().color()).name() == "#336699"
    assert QColor(_fmt_at(item, 8).foreground().color()).name() == "#336699"


def test_word_scope_does_not_restyle_other_words(qapp):
    scene = QGraphicsScene()
    item = CanvasTextItem("hello world")
    scene.addItem(item)
    item.enter_edit_mode()
    cursor = item.textCursor()
    cursor.setPosition(1)
    item.setTextCursor(cursor)
    item.apply_char_format(bold=True)
    assert _fmt_at(item, 0).fontWeight() == QFont.Weight.Bold
    assert _fmt_at(item, 8).fontWeight() != QFont.Weight.Bold
