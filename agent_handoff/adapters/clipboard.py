"""Grok-friendly clipboard JPEG and path handoff helpers."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QIODevice, QMimeData, QUrl, Qt
from PyQt6.QtGui import QImage, QPainter

CLIPBOARD_JPEG_MAX_SIDE = 1440
CLIPBOARD_JPEG_QUALITY = 88


def encoded_image_bytes(image: QImage, image_format: str, quality: int = -1) -> bytes | None:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, image_format, quality):
        return None
    return bytes(buffer.data())


def grok_clipboard_jpeg_image(image: QImage) -> QImage:
    if max(image.width(), image.height()) > CLIPBOARD_JPEG_MAX_SIDE:
        image = image.scaled(
            CLIPBOARD_JPEG_MAX_SIDE,
            CLIPBOARD_JPEG_MAX_SIDE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    if image.hasAlphaChannel():
        flattened = QImage(image.size(), QImage.Format.Format_RGB32)
        flattened.fill(Qt.GlobalColor.white)
        painter = QPainter(flattened)
        painter.drawImage(0, 0, image)
        painter.end()
        image = flattened
    return image.convertToFormat(QImage.Format.Format_RGB888)


def clipboard_image_mime_data(
    image: QImage, image_path: Path, as_jpeg: bool
) -> QMimeData | None:
    mime_data = QMimeData()
    if not as_jpeg:
        mime_data.setUrls([QUrl.fromLocalFile(str(image_path))])
    if as_jpeg:
        jpeg_image = grok_clipboard_jpeg_image(image)
        jpeg_bytes = encoded_image_bytes(jpeg_image, "JPEG", CLIPBOARD_JPEG_QUALITY)
        if jpeg_bytes is None:
            return None
        mime_data.setData("image/jpeg", QByteArray(jpeg_bytes))
        image_text = f"[Image from CanvasForge: {image_path.name}]"
    else:
        png_bytes = encoded_image_bytes(image, "PNG")
        if png_bytes is None:
            return None
        mime_data.setData("image/png", QByteArray(png_bytes))
        mime_data.setImageData(image)
        image_text = str(image_path)
    mime_data.setText(image_text)
    return mime_data
