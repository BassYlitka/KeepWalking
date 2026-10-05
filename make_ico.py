"""Build a square multi-size app icon without stretching the source picture."""

from __future__ import annotations

import ctypes
import struct
import sys
from pathlib import Path

SIZES = (16, 24, 32, 48, 64, 256)


class GdiplusStartupInput(ctypes.Structure):
    _fields_ = [
        ("GdiplusVersion", ctypes.c_uint),
        ("DebugEventCallback", ctypes.c_void_p),
        ("SuppressBackgroundThread", ctypes.c_int),
        ("SuppressExternalCodecs", ctypes.c_int),
    ]


class BitmapData(ctypes.Structure):
    _fields_ = [
        ("Width", ctypes.c_uint),
        ("Height", ctypes.c_uint),
        ("Stride", ctypes.c_int),
        ("PixelFormat", ctypes.c_int),
        ("Scan0", ctypes.c_void_p),
        ("Reserved", ctypes.c_void_p),
    ]


class GpRect(ctypes.Structure):
    _fields_ = [
        ("X", ctypes.c_int),
        ("Y", ctypes.c_int),
        ("Width", ctypes.c_int),
        ("Height", ctypes.c_int),
    ]


def _lib():
    lib = ctypes.WinDLL("gdiplus")
    lib.GdiplusStartup.argtypes = [ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(GdiplusStartupInput), ctypes.c_void_p]
    lib.GdiplusStartup.restype = ctypes.c_int
    lib.GdipCreateBitmapFromFile.argtypes = [ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipCreateBitmapFromFile.restype = ctypes.c_int
    lib.GdipGetImageWidth.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.GdipGetImageHeight.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
    lib.GdipCreateBitmapFromScan0.argtypes = [
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
    ]
    lib.GdipCreateBitmapFromScan0.restype = ctypes.c_int
    lib.GdipGetImageGraphicsContext.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    lib.GdipSetInterpolationMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetPixelOffsetMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipSetCompositingQuality.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.GdipGraphicsClear.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    lib.GdipDrawImageRectI.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    ]
    lib.GdipBitmapLockBits.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(GpRect), ctypes.c_uint, ctypes.c_int, ctypes.POINTER(BitmapData),
    ]
    lib.GdipBitmapLockBits.restype = ctypes.c_int
    lib.GdipBitmapUnlockBits.argtypes = [ctypes.c_void_p, ctypes.POINTER(BitmapData)]
    lib.GdipDeleteGraphics.argtypes = [ctypes.c_void_p]
    lib.GdipDisposeImage.argtypes = [ctypes.c_void_p]
    token = ctypes.c_ulong()
    startup = GdiplusStartupInput(1, None, 0, 0)
    if lib.GdiplusStartup(ctypes.byref(token), ctypes.byref(startup), None) != 0:
        raise OSError("gdiplus")
    return lib


def render_bgra(lib, src, src_w: int, src_h: int, size: int) -> bytes:
    dst = ctypes.c_void_p()
    if lib.GdipCreateBitmapFromScan0(size, size, 0, 0x26200A, None, ctypes.byref(dst)) != 0:
        raise OSError("bitmap")
    graphics = ctypes.c_void_p()
    lib.GdipGetImageGraphicsContext(dst, ctypes.byref(graphics))
    lib.GdipSetInterpolationMode(graphics, 7)
    lib.GdipSetPixelOffsetMode(graphics, 4)
    lib.GdipSetCompositingQuality(graphics, 2)
    lib.GdipGraphicsClear(graphics, 0)
    pad = 1 if size <= 24 else max(2, size // 32)
    avail = max(1, size - pad * 2)
    scale = min(avail / src_w, avail / src_h)
    draw_w = max(1, int(round(src_w * scale)))
    draw_h = max(1, int(round(src_h * scale)))
    lib.GdipDrawImageRectI(graphics, src, (size - draw_w) // 2, (size - draw_h) // 2, draw_w, draw_h)
    lib.GdipDeleteGraphics(graphics)
    data = BitmapData()
    rect = GpRect(0, 0, size, size)
    if lib.GdipBitmapLockBits(dst, ctypes.byref(rect), 1, 0x26200A, ctypes.byref(data)) != 0:
        lib.GdipDisposeImage(dst)
        raise OSError("lock")
    rows = []
    for y in range(size):
        row = ctypes.string_at(data.Scan0 + y * data.Stride, size * 4)
        rows.append(row)
    lib.GdipBitmapUnlockBits(dst, ctypes.byref(data))
    lib.GdipDisposeImage(dst)
    return b"".join(rows)


def _dib(size: int, topdown: bytes) -> bytes:
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    xor = b"".join(topdown[(size - 1 - y) * size * 4:(size - y) * size * 4] for y in range(size))
    mask_row = ((size + 31) // 32) * 4
    mask = b"\x00" * (mask_row * size)
    return header + xor + mask


def write_ico(src_path: Path, dest: Path) -> None:
    lib = _lib()
    image = ctypes.c_void_p()
    if lib.GdipCreateBitmapFromFile(str(src_path), ctypes.byref(image)) != 0:
        raise OSError(src_path)
    width = ctypes.c_uint()
    height = ctypes.c_uint()
    lib.GdipGetImageWidth(image, ctypes.byref(width))
    lib.GdipGetImageHeight(image, ctypes.byref(height))
    blobs = [render_bgra(lib, image, width.value, height.value, size) for size in SIZES]
    lib.GdipDisposeImage(image)
    count = len(SIZES)
    header = struct.pack("<HHH", 0, 1, count)
    entries = b""
    images = b""
    offset = 6 + 16 * count
    for size, pixels in zip(SIZES, blobs):
        dib = _dib(size, pixels)
        entries += struct.pack("<BBBBHHII", size if size < 256 else 0, size if size < 256 else 0, 0, 0, 1, 32, len(dib), offset)
        images += dib
        offset += len(dib)
    dest.write_bytes(header + entries + images)


if __name__ == "__main__":
    root = Path(__file__).resolve().parent
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "icons" / "game.png"
    dest = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "icons" / "app.ico"
    write_ico(src, dest)
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")
