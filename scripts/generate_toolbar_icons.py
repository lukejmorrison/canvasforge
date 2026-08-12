#!/usr/bin/env python3
"""Generate the Forge toolbar icon set (SVG + PNG) for CanvasForge.

Icons are 64x64, dark-mode first, with a shared ink outline and dual-tone
fills so they stay readable from 24px through 64px toolbar sizes.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import cairosvg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ICON_DIR = ROOT / "assets" / "toolbar_icons"
PLUGIN_COPIES = {
    "callout": ROOT / "plugins" / "callout" / "icon",
    "crop": ROOT / "plugins" / "crop_tool" / "icon",
}

INK = "#1c2030"
WHITE = "#f8fafc"
SLATE = "#94a3b8"
CYAN = "#7dd3fc"
BLUE = "#60a5fa"
SKY = "#38bdf8"
INDIGO = "#818cf8"
AMBER = "#fbbf24"
ORANGE = "#fb923c"
RED = "#f87171"
ROSE = "#fb7185"
GREEN = "#4ade80"
PURPLE = "#c084fc"
PINK = "#f472b6"
NAVY = "#334155"

STROKE = (
    f'stroke="{INK}" stroke-width="2.5" stroke-linejoin="round" '
    'stroke-linecap="round"'
)
STROKE_THIN = (
    f'stroke="{INK}" stroke-width="1.8" stroke-linejoin="round" '
    'stroke-linecap="round"'
)


def lg(gid: str, x1, y1, x2, y2, c1: str, c2: str) -> str:
    return (
        f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
        f'gradientUnits="userSpaceOnUse">'
        f'<stop offset="0" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/>'
        f"</linearGradient>"
    )


def doc(title: str, body: str, defs: str = "") -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        'width="64" height="64">\n'
        f"  <title>{title}</title>\n"
        f"  <defs>\n{defs}\n  </defs>\n"
        f"{body}\n"
        "</svg>\n"
    )


def icon_pointer() -> str:
    return doc(
        "Pointer — click and select items",
        f"""
  <path d="M18 12 L18 50 L28 40 L35 56 L43 52.5 L36 37 L50 37 Z"
        fill="url(#pointer-fill)" {STROKE}/>
  <path d="M22 18 L22 36 L28 31" fill="{CYAN}" opacity="0.45"/>
""",
        lg("pointer-fill", 18, 12, 46, 56, WHITE, "#c7d2fe"),
    )


def icon_selection() -> str:
    return doc(
        "Select — draw a marquee on the canvas",
        f"""
  <rect x="11" y="13" width="42" height="38" rx="3"
        fill="#38bdf8" fill-opacity="0.12"
        stroke="{CYAN}" stroke-width="2.6" stroke-dasharray="6 3.5"
        stroke-linecap="round"/>
  <rect x="8.5" y="10.5" width="7" height="7" rx="1.2" fill="{WHITE}" {STROKE_THIN}/>
  <rect x="48.5" y="10.5" width="7" height="7" rx="1.2" fill="{WHITE}" {STROKE_THIN}/>
  <rect x="8.5" y="46.5" width="7" height="7" rx="1.2" fill="{WHITE}" {STROKE_THIN}/>
  <rect x="48.5" y="46.5" width="7" height="7" rx="1.2" fill="{WHITE}" {STROKE_THIN}/>
""",
    )


def icon_cut() -> str:
    return doc(
        "Cutout — extract a region from an image",
        f"""
  <rect x="8" y="10" width="34" height="26" rx="3" fill="url(#cut-photo)" {STROKE}/>
  <path d="M12 28 C18 20 24 22 30 18 C36 14 38 20 40 16" fill="none"
        stroke="#bfdbfe" stroke-width="2.2" stroke-linecap="round"/>
  <rect x="18" y="16" width="16" height="12" rx="1.5" fill="none"
        stroke="{AMBER}" stroke-width="2" stroke-dasharray="3.5 2.2"/>
  <g transform="translate(2 4)">
    <path d="M22 34 L14 22" fill="none" stroke="{SLATE}" stroke-width="3.4" stroke-linecap="round"/>
    <path d="M30 34 L40 20" fill="none" stroke="{SLATE}" stroke-width="3.4" stroke-linecap="round"/>
    <circle cx="26" cy="38" r="3.2" fill="{WHITE}" {STROKE_THIN}/>
    <ellipse cx="16" cy="48" rx="6.5" ry="5" fill="none" stroke="{RED}" stroke-width="2.8"/>
    <ellipse cx="36" cy="48" rx="6.5" ry="5" fill="none" stroke="{BLUE}" stroke-width="2.8"/>
  </g>
""",
        lg("cut-photo", 8, 10, 42, 36, "#93c5fd", "#2563eb"),
    )


def icon_move() -> str:
    return doc(
        "Move — drag the selection in any direction",
        f"""
  <path d="M32 8 L40 18 H35 V26 H48 L58 32 L48 38 H35 V46 H40 L32 56 L24 46 H29 V38 H16 L6 32 L16 26 H29 V18 H24 Z"
        fill="url(#move-fill)" {STROKE}/>
""",
        lg("move-fill", 32, 8, 32, 56, WHITE, CYAN),
    )


def icon_rotate() -> str:
    return doc(
        "Rotate — spin the selected item",
        f"""
  <g transform="rotate(-18 32 34)">
    <rect x="18" y="22" width="24" height="24" rx="4" fill="url(#rotate-card)" {STROKE}/>
  </g>
  <path d="M20 18 A18 18 0 0 1 50 22" fill="none" stroke="url(#rotate-arc)"
        stroke-width="4" stroke-linecap="round"/>
  <path d="M50 22 L56 14 L44 16 Z" fill="{AMBER}" {STROKE_THIN}/>
""",
        lg("rotate-card", 18, 22, 42, 46, "#bfdbfe", BLUE)
        + lg("rotate-arc", 20, 10, 52, 24, AMBER, ORANGE),
    )


def icon_scale() -> str:
    return doc(
        "Scale — resize from the corners",
        f"""
  <rect x="20" y="20" width="24" height="24" rx="4" fill="url(#scale-card)" {STROKE}/>
  <g fill="none" stroke="{AMBER}" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M18 18 L10 10 M10 10 H17 M10 10 V17"/>
    <path d="M46 18 L54 10 M54 10 H47 M54 10 V17"/>
    <path d="M18 46 L10 54 M10 54 H17 M10 54 V47"/>
    <path d="M46 46 L54 54 M54 54 H47 M54 54 V47"/>
  </g>
""",
        lg("scale-card", 20, 20, 44, 44, "#e0f2fe", SKY),
    )


def icon_eraser() -> str:
    return doc(
        "Delete — remove the selected items",
        f"""
  <rect x="16" y="12" width="32" height="6" rx="2" fill="url(#trash-lid)" {STROKE}/>
  <rect x="28" y="8" width="8" height="6" rx="1.5" fill="{SLATE}" {STROKE_THIN}/>
  <path d="M18 20 H46 L43.5 52 A6 6 0 0 1 37.5 57 H26.5 A6 6 0 0 1 20.5 52 Z"
        fill="url(#trash-body)" {STROKE}/>
  <path d="M26 28 V48 M32 28 V48 M38 28 V48" fill="none"
        stroke="{INK}" stroke-width="2.2" stroke-linecap="round" opacity="0.55"/>
""",
        lg("trash-lid", 16, 12, 48, 18, ROSE, RED)
        + lg("trash-body", 18, 20, 44, 57, "#fda4af", "#e11d48"),
    )


def icon_snap_grid() -> str:
    return doc(
        "Snap Grid — align items to the grid",
        f"""
  <g stroke="{BLUE}" stroke-width="2.2" stroke-linecap="round" opacity="0.95">
    <path d="M14 18 H50 M14 32 H50 M14 46 H50"/>
    <path d="M18 12 V52 M32 12 V52 M46 12 V52"/>
  </g>
  <circle cx="32" cy="32" r="5.5" fill="{AMBER}" {STROKE}/>
  <circle cx="32" cy="32" r="2" fill="{WHITE}"/>
""",
    )


def icon_bring_forward() -> str:
    return doc(
        "Bring Forward — raise the selected layer",
        f"""
  <rect x="12" y="26" width="26" height="22" rx="3" fill="url(#bf-back)" {STROKE}/>
  <rect x="22" y="14" width="26" height="22" rx="3" fill="url(#bf-front)" {STROKE}/>
  <path d="M52 46 V22" fill="none" stroke="{AMBER}" stroke-width="3.4" stroke-linecap="round"/>
  <path d="M52 20 L46 28 L58 28 Z" fill="{AMBER}" {STROKE_THIN}/>
""",
        lg("bf-back", 12, 26, 38, 48, "#64748b", "#334155")
        + lg("bf-front", 22, 14, 48, 36, "#bfdbfe", BLUE),
    )


def icon_send_backward() -> str:
    return doc(
        "Send Backward — lower the selected layer",
        f"""
  <rect x="22" y="14" width="26" height="22" rx="3" fill="url(#sb-back)" {STROKE}/>
  <rect x="12" y="26" width="26" height="22" rx="3" fill="url(#sb-front)" {STROKE}/>
  <path d="M52 18 V42" fill="none" stroke="{AMBER}" stroke-width="3.4" stroke-linecap="round"/>
  <path d="M52 46 L46 38 L58 38 Z" fill="{AMBER}" {STROKE_THIN}/>
""",
        lg("sb-back", 22, 14, 48, 36, "#64748b", "#334155")
        + lg("sb-front", 12, 26, 38, 48, "#bfdbfe", BLUE),
    )


def icon_save_as() -> str:
    return doc(
        "Save Selected — export the current selection",
        f"""
  <rect x="12" y="8" width="32" height="24" rx="3" fill="url(#save-shot)" {STROKE}/>
  <rect x="16" y="12" width="24" height="16" rx="1.5" fill="none"
        stroke="{AMBER}" stroke-width="1.8" stroke-dasharray="3 2"/>
  <path d="M28 34 V48" fill="none" stroke="{GREEN}" stroke-width="3.6" stroke-linecap="round"/>
  <path d="M28 50 L20 40 H36 Z" fill="{GREEN}" {STROKE_THIN}/>
  <path d="M14 54 H50" fill="none" stroke="{SLATE}" stroke-width="3.4" stroke-linecap="round"/>
  <path d="M14 54 L18 58 H46 L50 54" fill="none" stroke="{SLATE}" stroke-width="3.4"
        stroke-linecap="round" stroke-linejoin="round"/>
""",
        lg("save-shot", 12, 8, 44, 32, "#93c5fd", "#2563eb"),
    )


def icon_send_to_agent() -> str:
    return doc(
        "Send to Agent — hand the image to an AI agent",
        f"""
  <rect x="6" y="28" width="22" height="16" rx="3" fill="url(#agent-shot)" {STROKE}/>
  <path d="M10 40 C14 34 18 36 22 32" fill="none" stroke="#bfdbfe" stroke-width="1.8" stroke-linecap="round"/>
  <path d="M12 36 L56 12 L30 40 L26 54 L30 40 L40 36 Z" fill="url(#agent-plane)" {STROKE}/>
  <path d="M30 40 L56 12" fill="none" stroke="{INK}" stroke-width="2" stroke-linecap="round"/>
  <path d="M50 8 L58 8 M54 4 L58 8 L54 12" fill="none" stroke="{AMBER}"
        stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
""",
        lg("agent-shot", 6, 28, 28, 44, "#93c5fd", INDIGO)
        + lg("agent-plane", 12, 12, 56, 48, AMBER, ORANGE),
    )


def icon_flatten_selected() -> str:
    return doc(
        "Flatten Selected — merge the chosen layers",
        f"""
  <rect x="11" y="10" width="42" height="44" rx="4" fill="none"
        stroke="{CYAN}" stroke-width="1.8" stroke-dasharray="4 2.5"/>
  <path d="M32 8 V16" fill="none" stroke="{AMBER}" stroke-width="3.2" stroke-linecap="round"/>
  <path d="M32 20 L25 12 H39 Z" fill="{AMBER}" {STROKE_THIN}/>
  <rect x="16" y="24" width="32" height="10" rx="2" fill="url(#fs-top)" {STROKE}/>
  <rect x="16" y="32" width="32" height="10" rx="2" fill="url(#fs-bot)" {STROKE}/>
  <path d="M32 56 V48" fill="none" stroke="{AMBER}" stroke-width="3.2" stroke-linecap="round"/>
  <path d="M32 44 L25 52 H39 Z" fill="{AMBER}" {STROKE_THIN}/>
""",
        lg("fs-top", 16, 24, 48, 34, "#bfdbfe", BLUE)
        + lg("fs-bot", 16, 32, 48, 42, "#cbd5e1", "#64748b"),
    )


def icon_flatten_all() -> str:
    return doc(
        "Flatten All — merge every layer into one",
        f"""
  <path d="M32 6 V14" fill="none" stroke="{AMBER}" stroke-width="3.2" stroke-linecap="round"/>
  <path d="M32 18 L25 10 H39 Z" fill="{AMBER}" {STROKE_THIN}/>
  <rect x="18" y="22" width="28" height="8" rx="2" fill="#93c5fd" {STROKE_THIN}/>
  <rect x="16" y="28" width="32" height="8" rx="2" fill="{BLUE}" {STROKE_THIN}/>
  <rect x="14" y="34" width="36" height="10" rx="2.5" fill="url(#fa-base)" {STROKE}/>
  <path d="M32 58 V50" fill="none" stroke="{AMBER}" stroke-width="3.2" stroke-linecap="round"/>
  <path d="M32 46 L25 54 H39 Z" fill="{AMBER}" {STROKE_THIN}/>
""",
        lg("fa-base", 14, 34, 50, 44, WHITE, SLATE),
    )


def icon_rectangle() -> str:
    return doc(
        "Rectangle — draw a rectangle annotation",
        f"""
  <rect x="12" y="16" width="40" height="32" rx="5" fill="url(#rect-fill)" {STROKE}/>
""",
        lg("rect-fill", 12, 16, 52, 48, "#e2e8f0", "#94a3b8"),
    )


def icon_ellipse() -> str:
    return doc(
        "Ellipse — draw an ellipse annotation",
        f"""
  <ellipse cx="32" cy="32" rx="22" ry="16" fill="url(#ell-fill)" {STROKE}/>
""",
        lg("ell-fill", 10, 16, 54, 48, "#bae6fd", SKY),
    )


def icon_arrow() -> str:
    return doc(
        "Arrow — draw a pointing annotation arrow",
        f"""
  <path d="M12 50 L34 28 L28 26 L54 12 L40 38 L38 32 Z"
        fill="url(#arrow-fill)" {STROKE}/>
""",
        lg("arrow-fill", 12, 50, 54, 12, "#ef4444", ROSE),
    )


def icon_step() -> str:
    return doc(
        "Step — place a numbered step marker",
        f"""
  <circle cx="32" cy="26" r="16" fill="url(#step-fill)" {STROKE}/>
  <path d="M22 40 L32 56 L42 40 Z" fill="url(#step-fill)" {STROKE}/>
  <path d="M27 22 L33.5 16 H37 V38 H31.5 V24 L27 26 Z" fill="{WHITE}"/>
""",
        lg("step-fill", 16, 10, 48, 56, "#93c5fd", "#2563eb"),
    )


def icon_blur() -> str:
    return doc(
        "Blur — soften a region of the image",
        f"""
  <rect x="10" y="10" width="18" height="18" rx="3" fill="#2563eb" {STROKE_THIN}/>
  <rect x="30" y="10" width="18" height="18" rx="3" fill="#dc2626" {STROKE_THIN}/>
  <rect x="10" y="30" width="18" height="18" rx="3" fill="#16a34a" {STROKE_THIN}/>
  <rect x="30" y="30" width="18" height="18" rx="3" fill="#d97706" {STROKE_THIN}/>
  <circle cx="46" cy="46" r="10" fill="#38bdf8" opacity="0.55"/>
  <circle cx="50" cy="42" r="8" fill="#f472b6" opacity="0.45"/>
  <circle cx="42" cy="50" r="7" fill="#fbbf24" opacity="0.5"/>
""",
    )


def icon_highlight() -> str:
    return doc(
        "Highlight — mark a region with a highlighter",
        f"""
  <path d="M8 20 H40" stroke="{SLATE}" stroke-width="2.3" stroke-linecap="round"/>
  <path d="M8 44 H36" stroke="{SLATE}" stroke-width="2.3" stroke-linecap="round"/>
  <rect x="8" y="27" width="30" height="11" rx="2" fill="{AMBER}" fill-opacity="0.9"/>
  <g transform="rotate(-38 42 30)">
    <rect x="36" y="8" width="13" height="24" rx="2.5" fill="url(#hl-body)" {STROKE}/>
    <rect x="36" y="18" width="13" height="4" fill="#f59e0b"/>
    <rect x="38.5" y="32" width="8" height="6" rx="1" fill="#78350f" {STROKE_THIN}/>
    <path d="M38.5 38 H46.5 L42.5 48 Z" fill="#451a03" {STROKE_THIN}/>
  </g>
""",
        lg("hl-body", 36, 8, 49, 32, "#fde68a", AMBER),
    )


def icon_border() -> str:
    return doc(
        "Border — add a frame around the selection",
        f"""
  <rect x="10" y="10" width="44" height="44" rx="5" fill="url(#bd-frame)" {STROKE}/>
  <rect x="18" y="18" width="28" height="28" rx="2" fill="url(#bd-photo)" {STROKE_THIN}/>
  <path d="M22 38 C26 30 30 32 34 28 C38 24 42 30 44 26"
        fill="none" stroke="#bfdbfe" stroke-width="2" stroke-linecap="round"/>
""",
        lg("bd-frame", 10, 10, 54, 54, WHITE, "#cbd5e1")
        + lg("bd-photo", 18, 18, 46, 46, "#60a5fa", "#1d4ed8"),
    )


def icon_colour_picker() -> str:
    return doc(
        "Eyedropper — sample a colour from the canvas",
        f"""
  <g transform="rotate(-45 30 28)">
    <ellipse cx="30" cy="12" rx="6.5" ry="5.5" fill="url(#drop-bulb)" {STROKE}/>
    <rect x="26.5" y="16" width="7" height="22" rx="1.6" fill="url(#drop-tube)" {STROKE}/>
    <path d="M26.5 38 H33.5 L30 50 Z" fill="{NAVY}" {STROKE_THIN}/>
  </g>
  <circle cx="48" cy="48" r="8" fill="url(#drop-well)" {STROKE}/>
  <circle cx="48" cy="48" r="3.5" fill="{WHITE}" opacity="0.35"/>
""",
        lg("drop-bulb", 24, 6, 36, 18, ROSE, RED)
        + lg("drop-tube", 26, 16, 34, 38, WHITE, SLATE)
        + lg("drop-well", 40, 40, 56, 56, "#fde68a", "#22c55e"),
    )


def icon_fill() -> str:
    return doc(
        "Fill — flood-fill a connected colour region",
        f"""
  <g transform="rotate(28 28 30)">
    <path d="M22 12 A8 8 0 0 1 38 12" fill="none" stroke="{SLATE}" stroke-width="3.4"
          stroke-linecap="round"/>
    <path d="M16 18 H40 L36 46 H20 Z" fill="url(#fill-body)" {STROKE}/>
    <path d="M16 18 H40 L38 26 H18 Z" fill="url(#fill-paint)" {STROKE_THIN}/>
  </g>
  <path d="M46 36 C54 44 54 52 48 56 C40 54 42 46 46 36 Z" fill="url(#fill-paint)" {STROKE}/>
""",
        lg("fill-body", 16, 18, 40, 46, "#cbd5e1", "#64748b")
        + lg("fill-paint", 16, 18, 54, 56, SKY, "#2563eb"),
    )


def icon_text() -> str:
    return doc(
        "Text — add a text label",
        f"""
  <path d="M12 12 H52 V21 H37 V50 H27 V21 H12 Z"
        fill="url(#text-fill)" {STROKE}/>
  <path d="M16 58 H48" fill="none" stroke="{CYAN}" stroke-width="3.2" stroke-linecap="round"/>
""",
        lg("text-fill", 12, 12, 52, 50, WHITE, "#c7d2fe"),
    )


def icon_crop() -> str:
    return doc(
        "Crop — trim an image to a region",
        f"""
  <rect x="18" y="18" width="28" height="28" rx="2" fill="url(#crop-photo)" {STROKE_THIN}/>
  <path d="M10 18 V50 H42" fill="none" stroke="{WHITE}" stroke-width="4.4"
        stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M54 46 V14 H22" fill="none" stroke="{CYAN}" stroke-width="4.4"
        stroke-linecap="round" stroke-linejoin="round"/>
""",
        lg("crop-photo", 18, 18, 46, 46, "#93c5fd", "#2563eb"),
    )


def icon_callout() -> str:
    return doc(
        "Callout — insert a speech-bubble callout",
        f"""
  <path d="M12 14 H46 A8 8 0 0 1 54 22 V36 A8 8 0 0 1 46 44 H30 L18 56 V44 H12 A8 8 0 0 1 4 36 V22 A8 8 0 0 1 12 14 Z"
        fill="url(#call-fill)" {STROKE} transform="translate(4 0)"/>
  <circle cx="24" cy="30" r="3.2" fill="{WHITE}"/>
  <circle cx="34" cy="30" r="3.2" fill="{WHITE}"/>
  <circle cx="44" cy="30" r="3.2" fill="{WHITE}"/>
""",
        lg("call-fill", 8, 14, 54, 56, "#93c5fd", "#2563eb"),
    )


def icon_open() -> str:
    return doc(
        "Open — load images from disk",
        f"""
  <path d="M10 24 V48 A4 4 0 0 0 14 52 H50 A4 4 0 0 0 54 48 V28 A4 4 0 0 0 50 24 H30 L24 18 H14 A4 4 0 0 0 10 22 Z"
        fill="url(#open-folder)" {STROKE}/>
  <rect x="28" y="14" width="18" height="14" rx="2" fill="url(#open-photo)" {STROKE_THIN}/>
""",
        lg("open-folder", 10, 18, 54, 52, AMBER, "#d97706")
        + lg("open-photo", 28, 14, 46, 28, "#bfdbfe", BLUE),
    )


def icon_paste() -> str:
    return doc(
        "Paste — place clipboard contents on the canvas",
        f"""
  <rect x="16" y="16" width="32" height="40" rx="4" fill="url(#paste-board)" {STROKE}/>
  <rect x="24" y="10" width="16" height="10" rx="3" fill="{SLATE}" {STROKE_THIN}/>
  <rect x="22" y="26" width="20" height="16" rx="2" fill="url(#paste-img)" {STROKE_THIN}/>
""",
        lg("paste-board", 16, 16, 48, 56, WHITE, "#e2e8f0")
        + lg("paste-img", 22, 26, 42, 42, "#93c5fd", "#2563eb"),
    )


def icon_undo() -> str:
    return doc(
        "Undo — reverse the last action",
        f"""
  <path d="M46 40 A16 16 0 1 0 20 24" fill="none" stroke="url(#undo-arc)"
        stroke-width="5.5" stroke-linecap="round"/>
  <path d="M20 24 L10 22 L18 14 Z" fill="{CYAN}" {STROKE_THIN}/>
""",
        lg("undo-arc", 12, 16, 50, 48, CYAN, BLUE),
    )


def icon_redo() -> str:
    return doc(
        "Redo — restore the last undone action",
        f"""
  <path d="M18 40 A16 16 0 1 1 44 24" fill="none" stroke="url(#redo-arc)"
        stroke-width="5.5" stroke-linecap="round"/>
  <path d="M44 24 L54 22 L46 14 Z" fill="{GREEN}" {STROKE_THIN}/>
""",
        lg("redo-arc", 14, 16, 52, 48, GREEN, "#22c55e"),
    )


ICONS = {
    "toolbar_icon_pointer": icon_pointer,
    "toolbar_icon_selection": icon_selection,
    "toolbar_icon_cut": icon_cut,
    "toolbar_icon_move": icon_move,
    "toolbar_icon_rotate": icon_rotate,
    "toolbar_icon_scale": icon_scale,
    "toolbar_icon_eraser": icon_eraser,
    "toolbar_icon_delete": icon_eraser,
    "toolbar_icon_snap_grid": icon_snap_grid,
    "toolbar_icon_bring_forward": icon_bring_forward,
    "toolbar_icon_send_backward": icon_send_backward,
    "toolbar_icon_save_as": icon_save_as,
    "toolbar_icon_send_to_agent": icon_send_to_agent,
    "toolbar_icon_flatten_selected": icon_flatten_selected,
    "toolbar_icon_flatten_all": icon_flatten_all,
    "toolbar_icon_rectangle": icon_rectangle,
    "toolbar_icon_ellipse": icon_ellipse,
    "toolbar_icon_arrow": icon_arrow,
    "toolbar_icon_step": icon_step,
    "toolbar_icon_blur": icon_blur,
    "toolbar_icon_highlight": icon_highlight,
    "toolbar_icon_border": icon_border,
    "toolbar_icon_colour_picker": icon_colour_picker,
    "toolbar_icon_fill": icon_fill,
    "toolbar_icon_text": icon_text,
    "toolbar_icon_crop": icon_crop,
    "toolbar_icon_plugin_crop_tool_crop": icon_crop,
    "toolbar_icon_callout": icon_callout,
    "toolbar_icon_open": icon_open,
    "toolbar_icon_paste": icon_paste,
    "toolbar_icon_undo": icon_undo,
    "toolbar_icon_redo": icon_redo,
}

PREVIEW_ORDER = [
    "toolbar_icon_pointer",
    "toolbar_icon_save_as",
    "toolbar_icon_send_to_agent",
    "toolbar_icon_selection",
    "toolbar_icon_cut",
    "toolbar_icon_move",
    "toolbar_icon_rotate",
    "toolbar_icon_scale",
    "toolbar_icon_eraser",
    "toolbar_icon_snap_grid",
    "toolbar_icon_bring_forward",
    "toolbar_icon_send_backward",
    "toolbar_icon_flatten_selected",
    "toolbar_icon_flatten_all",
    "toolbar_icon_rectangle",
    "toolbar_icon_ellipse",
    "toolbar_icon_arrow",
    "toolbar_icon_step",
    "toolbar_icon_blur",
    "toolbar_icon_highlight",
    "toolbar_icon_border",
    "toolbar_icon_colour_picker",
    "toolbar_icon_fill",
    "toolbar_icon_text",
    "toolbar_icon_crop",
    "toolbar_icon_callout",
    "toolbar_icon_open",
    "toolbar_icon_paste",
    "toolbar_icon_undo",
    "toolbar_icon_redo",
]


def write_png(svg_text: str, dest: Path, size: int = 128) -> None:
    cairosvg.svg2png(
        bytestring=svg_text.encode("utf-8"),
        write_to=str(dest),
        output_width=size,
        output_height=size,
        background_color="rgba(0,0,0,0)",
    )


def label_for(name: str) -> str:
    return name.replace("toolbar_icon_", "").replace("_", " ")


def write_preview(png_paths: dict[str, Path], dest: Path) -> None:
    cols = 6
    cell = 160
    pad = 16
    rows = (len(PREVIEW_ORDER) + cols - 1) // cols
    width = cols * cell + pad * 2
    height = rows * cell + pad * 2 + 36
    img = Image.new("RGBA", (width, height), (30, 32, 40, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 13)
        title_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
        title_font = font
    draw.text((pad, 10), "CanvasForge Forge toolbar icons", fill=(248, 250, 252), font=title_font)

    for i, name in enumerate(PREVIEW_ORDER):
        r, c = divmod(i, cols)
        x = pad + c * cell
        y = pad + 36 + r * cell
        icon = Image.open(png_paths[name]).convert("RGBA").resize((96, 96), Image.Resampling.LANCZOS)
        img.alpha_composite(icon, (x + 32, y + 8))
        label = label_for(name)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        draw.text((x + (cell - tw) / 2, y + 112), label, fill=(203, 213, 225), font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest)


def main() -> None:
    ICON_DIR.mkdir(parents=True, exist_ok=True)
    png_paths: dict[str, Path] = {}
    for name, factory in ICONS.items():
        svg_text = factory()
        svg_path = ICON_DIR / f"{name}.svg"
        png_path = ICON_DIR / f"{name}.png"
        svg_path.write_text(svg_text, encoding="utf-8")
        write_png(svg_text, png_path)
        png_paths[name] = png_path
        print(f"wrote {svg_path.name} + {png_path.name}")

    for key, dest_stem in PLUGIN_COPIES.items():
        src_svg = ICON_DIR / f"toolbar_icon_{key}.svg"
        src_png = ICON_DIR / f"toolbar_icon_{key}.png"
        dest_stem.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_svg, dest_stem.with_suffix(".svg"))
        shutil.copyfile(src_png, dest_stem.with_suffix(".png"))
        print(f"copied plugin icon {dest_stem}")

    preview = ICON_DIR / "forge_icon_preview.png"
    write_preview(png_paths, preview)
    print(f"wrote preview {preview}")


if __name__ == "__main__":
    main()
