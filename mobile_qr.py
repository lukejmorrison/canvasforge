"""Compact QR Code encoder (byte mode, ECC M) for local pairing payloads.

No third-party dependency. Versions 1–10 cover a LAN pairing URL plus token.
"""

from __future__ import annotations

from typing import List, Sequence

# GF(256) for QR: primitive polynomial 0x11D.
_EXP = [0] * 512
_LOG = [0] * 256
_val = 1
for _i in range(255):
    _EXP[_i] = _val
    _LOG[_val] = _i
    _val <<= 1
    if _val & 0x100:
        _val ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _gf_pow(a: int, power: int) -> int:
    if a == 0:
        return 0
    return _EXP[(_LOG[a] * power) % 255]


def _poly_mul(p: Sequence[int], q: Sequence[int]) -> List[int]:
    out = [0] * (len(p) + len(q) - 1)
    for i, a in enumerate(p):
        for j, b in enumerate(q):
            out[i + j] ^= _gf_mul(a, b)
    return out


def _rs_generator(ec_count: int) -> List[int]:
    gen = [1]
    for i in range(ec_count):
        gen = _poly_mul(gen, [1, _gf_pow(2, i)])
    return gen


def _rs_encode(data: Sequence[int], ec_count: int) -> List[int]:
    gen = _rs_generator(ec_count)
    result = list(data) + [0] * ec_count
    for i in range(len(data)):
        coef = result[i]
        if coef == 0:
            continue
        for j in range(1, len(gen)):
            result[i + j] ^= _gf_mul(gen[j], coef)
    return result[len(data) :]


# version -> (total_codewords, ec_codewords_per_block, group1_blocks, group1_data, group2_blocks, group2_data)
# ECC level M. From ISO/IEC 18004 tables.
_VERSION_M = {
    1: (26, 10, 1, 16, 0, 0),
    2: (44, 16, 1, 28, 0, 0),
    3: (70, 26, 1, 44, 0, 0),
    4: (100, 18, 2, 32, 0, 0),
    5: (134, 24, 2, 43, 0, 0),
    6: (172, 16, 4, 27, 0, 0),
    7: (196, 18, 4, 31, 0, 0),
    8: (242, 22, 2, 38, 2, 39),
    9: (292, 22, 3, 36, 2, 37),
    10: (346, 26, 4, 43, 1, 44),
}

_ALIGN_CENTERS = {
    2: (6, 18),
    3: (6, 22),
    4: (6, 26),
    5: (6, 30),
    6: (6, 34),
    7: (6, 22, 38),
    8: (6, 24, 42),
    9: (6, 26, 46),
    10: (6, 28, 50),
}

# Format bits for ECC M (01) and masks 0–7, already with BCH, XOR 0x5412.
_FORMAT_M = {
    0: 0x5412,
    1: 0x5125,
    2: 0x5E7C,
    3: 0x5B4B,
    4: 0x45F9,
    5: 0x40CE,
    6: 0x4F97,
    7: 0x4AA0,
}


def _version_size(version: int) -> int:
    return 17 + 4 * version


def _data_capacity_bytes(version: int) -> int:
    total, _ec, g1b, g1d, g2b, g2d = _VERSION_M[version]
    data_cw = g1b * g1d + g2b * g2d
    # Byte mode: 4 mode bits + 8/16 count bits + data + terminator, packed into data_cw bytes.
    count_bits = 8 if version < 10 else 16
    usable_bits = data_cw * 8 - 4 - count_bits
    return usable_bits // 8


def choose_version(payload: bytes) -> int:
    for version in range(1, 11):
        if len(payload) <= _data_capacity_bytes(version):
            return version
    raise ValueError("Pairing payload is too long for a local QR code")


def _encode_data(payload: bytes, version: int) -> List[int]:
    total, _ec, g1b, g1d, g2b, g2d = _VERSION_M[version]
    data_cw = g1b * g1d + g2b * g2d
    count_bits = 8 if version < 10 else 16
    bits: List[int] = []

    def put(value: int, width: int) -> None:
        for shift in range(width - 1, -1, -1):
            bits.append((value >> shift) & 1)

    put(0b0100, 4)  # byte mode
    put(len(payload), count_bits)
    for byte in payload:
        put(byte, 8)
    # Terminator (up to 4 zero bits)
    remaining = data_cw * 8 - len(bits)
    put(0, min(4, remaining))
    while len(bits) % 8 != 0:
        bits.append(0)
    data = []
    for i in range(0, len(bits), 8):
        byte = 0
        for bit in bits[i : i + 8]:
            byte = (byte << 1) | bit
        data.append(byte)
    pad = (0xEC, 0x11)
    pad_i = 0
    while len(data) < data_cw:
        data.append(pad[pad_i])
        pad_i ^= 1
    return data


def _interleave(data: List[int], version: int) -> List[int]:
    _total, ec, g1b, g1d, g2b, g2d = _VERSION_M[version]
    blocks: List[List[int]] = []
    ec_blocks: List[List[int]] = []
    offset = 0
    for _ in range(g1b):
        block = data[offset : offset + g1d]
        offset += g1d
        blocks.append(block)
        ec_blocks.append(_rs_encode(block, ec))
    for _ in range(g2b):
        block = data[offset : offset + g2d]
        offset += g2d
        blocks.append(block)
        ec_blocks.append(_rs_encode(block, ec))
    out: List[int] = []
    for i in range(max(g1d, g2d)):
        for block in blocks:
            if i < len(block):
                out.append(block[i])
    for i in range(ec):
        for block in ec_blocks:
            out.append(block[i])
    return out


def _finder(grid: List[List[int]], reserved: List[List[int]], row: int, col: int) -> None:
    pattern = (
        0b1111111,
        0b1000001,
        0b1011101,
        0b1011101,
        0b1011101,
        0b1000001,
        0b1111111,
    )
    size = len(grid)
    for r in range(-1, 8):
        for c in range(-1, 8):
            rr, cc = row + r, col + c
            if 0 <= rr < size and 0 <= cc < size:
                reserved[rr][cc] = 1
                if 0 <= r <= 6 and 0 <= c <= 6:
                    grid[rr][cc] = (pattern[r] >> (6 - c)) & 1
                else:
                    grid[rr][cc] = 0


def _alignment(grid: List[List[int]], reserved: List[List[int]], row: int, col: int) -> None:
    pattern = (
        0b11111,
        0b10001,
        0b10101,
        0b10001,
        0b11111,
    )
    for r in range(5):
        for c in range(5):
            rr, cc = row - 2 + r, col - 2 + c
            reserved[rr][cc] = 1
            grid[rr][cc] = (pattern[r] >> (4 - c)) & 1


def _place_function_patterns(grid: List[List[int]], reserved: List[List[int]], version: int) -> None:
    size = len(grid)
    _finder(grid, reserved, 0, 0)
    _finder(grid, reserved, 0, size - 7)
    _finder(grid, reserved, size - 7, 0)
    for i in range(8, size - 8):
        bit = 1 if i % 2 == 0 else 0
        if not reserved[6][i]:
            grid[6][i] = bit
            reserved[6][i] = 1
        if not reserved[i][6]:
            grid[i][6] = bit
            reserved[i][6] = 1
    for center_r in _ALIGN_CENTERS.get(version, ()):
        for center_c in _ALIGN_CENTERS.get(version, ()):
            if reserved[center_r][center_c]:
                continue
            _alignment(grid, reserved, center_r, center_c)
    # Dark module
    grid[size - 8][8] = 1
    reserved[size - 8][8] = 1
    # Reserve format info
    for i in range(9):
        reserved[8][i] = 1
        reserved[i][8] = 1
    for i in range(8):
        reserved[8][size - 1 - i] = 1
        reserved[size - 1 - i][8] = 1
    reserved[8][8] = 1


def _mask_bit(mask: int, row: int, col: int) -> int:
    if mask == 0:
        return int((row + col) % 2 == 0)
    if mask == 1:
        return int(row % 2 == 0)
    if mask == 2:
        return int(col % 3 == 0)
    if mask == 3:
        return int((row + col) % 3 == 0)
    if mask == 4:
        return int((row // 2 + col // 3) % 2 == 0)
    if mask == 5:
        return int((row * col) % 2 + (row * col) % 3 == 0)
    if mask == 6:
        return int(((row * col) % 2 + (row * col) % 3) % 2 == 0)
    return int(((row + col) % 2 + (row * col) % 3) % 2 == 0)


def _place_data(grid: List[List[int]], reserved: List[List[int]], codewords: Sequence[int], mask: int) -> None:
    size = len(grid)
    bits: List[int] = []
    for byte in codewords:
        for shift in range(7, -1, -1):
            bits.append((byte >> shift) & 1)
    # Remainder bits for some versions
    remainder = {2: 7, 3: 7, 4: 7, 5: 7, 6: 7, 7: 0, 8: 0, 9: 0, 10: 0}.get(
        (size - 17) // 4, 0
    )
    bits.extend([0] * remainder)
    index = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if reserved[row][c]:
                    continue
                bit = bits[index] if index < len(bits) else 0
                index += 1
                grid[row][c] = bit ^ _mask_bit(mask, row, c)
        upward = not upward
        col -= 2


def _apply_format(grid: List[List[int]], mask: int) -> None:
    bits = _FORMAT_M[mask]
    size = len(grid)
    coords_a = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
                (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    coords_b = [(size - 1, 8), (size - 2, 8), (size - 3, 8), (size - 4, 8),
                (size - 5, 8), (size - 6, 8), (size - 7, 8), (8, size - 8),
                (8, size - 7), (8, size - 6), (8, size - 5), (8, size - 4),
                (8, size - 3), (8, size - 2), (8, size - 1)]
    for i, (r, c) in enumerate(coords_a):
        grid[r][c] = (bits >> (14 - i)) & 1
    for i, (r, c) in enumerate(coords_b):
        grid[r][c] = (bits >> (14 - i)) & 1


def _penalty(grid: List[List[int]]) -> int:
    size = len(grid)
    score = 0
    for row in range(size):
        run = 1
        for col in range(1, size):
            if grid[row][col] == grid[row][col - 1]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    for col in range(size):
        run = 1
        for row in range(1, size):
            if grid[row][col] == grid[row - 1][col]:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run = 1
        if run >= 5:
            score += 3 + (run - 5)
    for row in range(size - 1):
        for col in range(size - 1):
            if grid[row][col] == grid[row][col + 1] == grid[row + 1][col] == grid[row + 1][col + 1]:
                score += 3
    finder = (1, 0, 1, 1, 1, 0, 1)
    for row in range(size):
        line = grid[row]
        for col in range(size - 6):
            if tuple(line[col : col + 7]) == finder:
                score += 40
    for col in range(size):
        line = [grid[row][col] for row in range(size)]
        for row in range(size - 6):
            if tuple(line[row : row + 7]) == finder:
                score += 40
    dark = sum(sum(row) for row in grid)
    percent = abs((dark * 100) // (size * size) - 50) // 5
    score += percent * 10
    return score


def qr_matrix(payload: str | bytes) -> List[List[int]]:
    """Return a square 0/1 matrix for ``payload`` (UTF-8 if str)."""
    data = payload.encode("utf-8") if isinstance(payload, str) else payload
    version = choose_version(data)
    encoded = _encode_data(data, version)
    codewords = _interleave(encoded, version)
    size = _version_size(version)
    best = None
    best_score = None
    for mask in range(8):
        grid = [[0] * size for _ in range(size)]
        reserved = [[0] * size for _ in range(size)]
        _place_function_patterns(grid, reserved, version)
        _place_data(grid, reserved, codewords, mask)
        _apply_format(grid, mask)
        score = _penalty(grid)
        if best_score is None or score < best_score:
            best = grid
            best_score = score
    assert best is not None
    return best


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
