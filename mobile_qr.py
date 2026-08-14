"""QR Code helper for local pairing payloads.

Uses a vendored segno encoder so Settings can show a scannable QR without
adding an Arch package. Pairing still works with the pasteable host:port#token
code if a camera cannot read the symbol.
"""

from __future__ import annotations

from typing import List, Sequence

from vendor.segno import encoder as segno_encoder


def choose_version(payload: bytes) -> int:
    code = segno_encoder.encode(payload, error="m", micro=False)
    return int(code.version)


def qr_matrix(payload: str | bytes) -> List[List[int]]:
    """Return a square 0/1 matrix for ``payload`` (UTF-8 if str)."""
    code = segno_encoder.encode(payload, error="m", micro=False)
    matrix: List[List[int]] = []
    for row in code.matrix:
        matrix.append([1 if module else 0 for module in row])
    return matrix


def qr_has_finder_patterns(matrix: Sequence[Sequence[int]]) -> bool:
    """True when the three QR finder patterns sit in the usual corners."""
    size = len(matrix)
    if size < 21 or size != len(matrix[0]):
        return False

    def is_finder(row: int, col: int) -> bool:
        for r in range(7):
            for c in range(7):
                on_ring = r in (0, 6) or c in (0, 6)
                in_core = 2 <= r <= 4 and 2 <= c <= 4
                expected = 1 if on_ring or in_core else 0
                if matrix[row + r][col + c] != expected:
                    return False
        return True

    return is_finder(0, 0) and is_finder(0, size - 7) and is_finder(size - 7, 0)
