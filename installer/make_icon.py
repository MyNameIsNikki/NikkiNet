# -*- coding: utf-8 -*-
"""Generate installer/nikkinet.ico (multi-size, BMP entries) with stdlib only.

Design: rounded square with a navy -> teal gradient and a white letter "N".
Rendered with 2x supersampling for smooth edges.
"""
import struct

SIZES = (16, 24, 32, 48, 64, 128, 256)
SS = 3  # supersampling factor

C1 = (26, 34, 74)      # top-left navy
C2 = (0, 173, 164)     # bottom-right teal


def render_rgba(size):
    b = size * SS
    half = b / 2.0
    r = b * 0.22
    nx0, nx1 = 0.28 * b, 0.42 * b
    nx2, nx3 = 0.58 * b, 0.72 * b
    ny0, ny1 = 0.28 * b, 0.72 * b
    diag_hw = 0.075 * b

    def inside_round(x, y):
        dx = abs(x - half)
        dy = abs(y - half)
        qx = max(dx - (half - r), 0.0)
        qy = max(dy - (half - r), 0.0)
        return dx <= half and dy <= half and (qx * qx + qy * qy) <= r * r

    def is_letter(x, y):
        if not (ny0 <= y <= ny1):
            return False
        if nx0 <= x <= nx1 or nx2 <= x <= nx3:
            return True
        t = (y - ny0) / (ny1 - ny0)
        cx = nx0 + t * (nx3 - nx0)
        return abs(x - cx) <= diag_hw

    hi = []  # b x b RGBA
    for y in range(b):
        row = []
        for x in range(b):
            fx, fy = x + 0.5, y + 0.5
            if not inside_round(fx, fy):
                row.append((0, 0, 0, 0))
                continue
            t = (x + y) / (2.0 * b)
            if is_letter(fx, fy):
                row.append((255, 255, 255, 255))
            else:
                row.append((
                    int(C1[0] + (C2[0] - C1[0]) * t),
                    int(C1[1] + (C2[1] - C1[1]) * t),
                    int(C1[2] + (C2[2] - C1[2]) * t),
                    255,
                ))
        hi.append(row)

    out = []
    for y in range(size):
        row = []
        for x in range(size):
            ra = ga = ba = aa = 0
            for yy in range(y * SS, (y + 1) * SS):
                for xx in range(x * SS, (x + 1) * SS):
                    p = hi[yy][xx]
                    ra += p[0] * p[3]
                    ga += p[1] * p[3]
                    ba += p[2] * p[3]
                    aa += p[3]
            n = SS * SS
            if aa:
                row.append((ra // aa, ga // aa, ba // aa, aa // n))
            else:
                row.append((0, 0, 0, 0))
        out.append(row)
    return out


def bmp_entry(rgba):
    size = len(rgba)
    # BITMAPINFOHEADER: height doubled (XOR + AND mask)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         size * size * 4, 0, 0, 0, 0)
    pixels = bytearray()
    for y in range(size - 1, -1, -1):
        for (r, g, b, a) in rgba[y]:
            pixels += bytes((b, g, r, a))
    mask_row = ((size + 31) // 32) * 4
    mask = b"\x00" * (mask_row * size)
    data = header + bytes(pixels) + mask
    return data


def build_ico():
    images = [bmp_entry(render_rgba(s)) for s in SIZES]
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    entries = b""
    for size, data in zip(SIZES, images):
        w = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    return header + entries + b"".join(images)


def main():
    import os
    ico = build_ico()
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nikkinet.ico")
    with open(out, "wb") as f:
        f.write(ico)
    print("written", out, len(ico), "bytes")


if __name__ == "__main__":
    main()
