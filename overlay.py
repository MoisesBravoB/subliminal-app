import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import random
import tkinter as tk
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Curated, highly legible fonts available on Windows
RECOMMENDED_FONTS: dict[str, list[str]] = {
    "Moderna (Estilo Apple)": ["SegUIVar.ttf", "seguisb.ttf", "segoeuib.ttf", "arialbd.ttf"],
    "Limpia (Segoe UI)": ["segoeuib.ttf", "segoeui.ttf", "arialbd.ttf"],
    "Geométrica (Bahnschrift)": ["bahnschrift.ttf", "segoeuib.ttf", "arialbd.ttf"],
    "Suave (Calibri)": ["calibrib.ttf", "calibri.ttf", "segoeuib.ttf"],
    "Universal (Arial)": ["arialbd.ttf", "arial.ttf"],
    "Editorial (Georgia)": ["georgiab.ttf", "georgia.ttf", "timesbd.ttf"],
}
DEFAULT_FONT_KEY = "Moderna (Estilo Apple)"

# Win32 constants
WS_POPUP = 0x80000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOPMOST = 0x00000008

HWND_TOPMOST = -1
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SW_HIDE = 0

AC_SRC_OVER = 0x00
AC_SRC_ALPHA = 0x01
ULW_ALPHA = 0x02
DIB_RGB_COLORS = 0
BI_RGB = 0


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_ubyte),
        ("BlendFlags", ctypes.c_ubyte),
        ("SourceConstantAlpha", ctypes.c_ubyte),
        ("AlphaFormat", ctypes.c_ubyte),
    ]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wintypes.DWORD * 3)]


if os.name == "nt":
    _user32 = ctypes.windll.user32
    _gdi32 = ctypes.windll.gdi32

    _user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    _user32.CreateWindowExW.restype = wintypes.HWND
    _user32.DestroyWindow.argtypes = [wintypes.HWND]
    _user32.DestroyWindow.restype = wintypes.BOOL
    _user32.GetDC.argtypes = [wintypes.HWND]
    _user32.GetDC.restype = wintypes.HDC
    _user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    _user32.ReleaseDC.restype = ctypes.c_int
    _user32.UpdateLayeredWindow.argtypes = [
        wintypes.HWND,
        wintypes.HDC,
        ctypes.POINTER(POINT),
        ctypes.POINTER(SIZE),
        wintypes.HDC,
        ctypes.POINTER(POINT),
        wintypes.COLORREF,
        ctypes.POINTER(BLENDFUNCTION),
        wintypes.DWORD,
    ]
    _user32.UpdateLayeredWindow.restype = wintypes.BOOL
    _user32.SetWindowPos.argtypes = [
        wintypes.HWND,
        wintypes.HWND,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_uint,
    ]
    _user32.SetWindowPos.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL

    _gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
    _gdi32.CreateCompatibleDC.restype = wintypes.HDC
    _gdi32.DeleteDC.argtypes = [wintypes.HDC]
    _gdi32.DeleteDC.restype = wintypes.BOOL
    _gdi32.CreateDIBSection.argtypes = [
        wintypes.HDC,
        ctypes.POINTER(BITMAPINFO),
        ctypes.c_uint,
        ctypes.POINTER(ctypes.c_void_p),
        wintypes.HANDLE,
        wintypes.DWORD,
    ]
    _gdi32.CreateDIBSection.restype = wintypes.HBITMAP
    _gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    _gdi32.SelectObject.restype = wintypes.HGDIOBJ
    _gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    _gdi32.DeleteObject.restype = wintypes.BOOL


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    c = hex_color.lstrip("#")
    if len(c) != 6:
        return (255, 255, 255)
    try:
        return (int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16))
    except ValueError:
        return (255, 255, 255)


def _load_truetype_font(font_key: str, size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    win_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    files = RECOMMENDED_FONTS.get(font_key, RECOMMENDED_FONTS[DEFAULT_FONT_KEY])
    for fname in list(files) + ["segoeuib.ttf", "arialbd.ttf", "arial.ttf"]:
        path = win_fonts / fname
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size_px)
            except Exception:
                continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        test = f"{current} {word}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            current = test
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def render_message_rgba(
    text: str,
    font_key: str,
    font_size_pt: int,
    text_color: str,
    bg_style: str,
    max_width: int,
) -> Image.Image:
    size_px = max(14, int(round(font_size_pt * 1.333)))
    font = _load_truetype_font(font_key, size_px)

    dummy = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    draw = ImageDraw.Draw(dummy)
    lines = _wrap_text(draw, text, font, max_width)

    line_bboxes = [draw.textbbox((0, 0), line, font=font) for line in lines]
    line_widths = [max(1, b[2] - b[0]) for b in line_bboxes]
    line_heights = [max(1, b[3] - b[1]) for b in line_bboxes]
    line_gap = max(6, int(size_px * 0.22))

    text_w = max(line_widths)
    text_h = sum(line_heights) + line_gap * (len(lines) - 1)

    pad_x = 30 if bg_style == "pill" else 14
    pad_y = 16 if bg_style == "pill" else 12
    img_w = text_w + pad_x * 2
    img_h = text_h + pad_y * 2

    img = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if bg_style == "pill":
        radius = min(22, img_h // 2)
        draw.rounded_rectangle(
            (0, 0, img_w - 1, img_h - 1),
            radius=radius,
            fill=(24, 24, 27, 232),
            outline=(72, 72, 78, 200),
            width=1,
        )

    r, g, b = _hex_to_rgb(text_color)
    cur_y = pad_y
    for line, bbox, lw, lh in zip(lines, line_bboxes, line_widths, line_heights):
        x = (img_w - lw) // 2 - bbox[0]
        y = cur_y - bbox[1]
        draw.text((x, y), line, font=font, fill=(r, g, b, 255))
        cur_y += lh + line_gap

    return img


def render_preview_image(text: str, cfg: dict[str, Any], box_w: int = 400, box_h: int = 84) -> Image.Image:
    """Render a WYSIWYG preview of the subliminal message onto a neutral desktop backdrop."""
    # Subtle neutral dark-to-mid gradient backdrop so both light and dark text are easy to judge
    bg = Image.new("RGBA", (box_w, box_h), (52, 54, 58, 255))
    draw = ImageDraw.Draw(bg)
    # Subtle checkerboard hint to convey transparency
    tile = 12
    for y in range(0, box_h, tile):
        for x in range(0, box_w, tile):
            if ((x // tile) + (y // tile)) % 2 == 0:
                draw.rectangle((x, y, x + tile - 1, y + tile - 1), fill=(62, 64, 69, 255))

    font_key = cfg.get("font_family", DEFAULT_FONT_KEY)
    font_size = int(cfg.get("font_size", 42))
    text_color = cfg.get("text_color", "#FFFFFF")
    bg_style = cfg.get("bg_style", "pill")
    opacity = max(0.05, min(1.0, float(cfg.get("opacity", 0.80))))

    # Render at actual font proportion, then fit smoothly inside the preview box
    msg_img = render_message_rgba(text or "Vista previa del mensaje", font_key, font_size, text_color, bg_style, max_width=900)

    # Apply master opacity
    if opacity < 1.0:
        r, g, b, a = msg_img.split()
        a = a.point(lambda p: int(round(p * opacity)))
        msg_img = Image.merge("RGBA", (r, g, b, a))

    # Scale down only if larger than the preview box
    max_pw = box_w - 16
    max_ph = box_h - 12
    mw, mh = msg_img.size
    scale = min(1.0, max_pw / max(1, mw), max_ph / max(1, mh))
    if scale < 1.0:
        new_size = (max(1, int(mw * scale)), max(1, int(mh * scale)))
        msg_img = msg_img.resize(new_size, Image.Resampling.LANCZOS)

    px = (box_w - msg_img.width) // 2
    py = (box_h - msg_img.height) // 2
    bg.alpha_composite(msg_img, (px, py))
    return bg.convert("RGB")


def _rgba_to_premultiplied_bgra(img: Image.Image) -> bytes:
    """Convert RGBA PIL image to premultiplied BGRA bytes for Windows UpdateLayeredWindow."""
    r, g, b, a = img.split()
    a_bytes = a.tobytes()
    r_bytes = r.tobytes()
    g_bytes = g.tobytes()
    b_bytes = b.tobytes()
    out = bytearray(len(a_bytes) * 4)
    for i, alpha in enumerate(a_bytes):
        j = i * 4
        if alpha == 255:
            out[j] = b_bytes[i]
            out[j + 1] = g_bytes[i]
            out[j + 2] = r_bytes[i]
            out[j + 3] = 255
        elif alpha > 0:
            out[j] = (b_bytes[i] * alpha) // 255
            out[j + 1] = (g_bytes[i] * alpha) // 255
            out[j + 2] = (r_bytes[i] * alpha) // 255
            out[j + 3] = alpha
    return bytes(out)


class SubliminalOverlay:
    """Native Win32 per-pixel alpha, click-through, non-activating always-on-top overlay."""

    def __init__(self, root: tk.Tk):
        self.root = root
        self._hide_after_id: str | None = None
        self._timer_period_set = False
        self._hwnd: int = 0
        self._setup_high_res_timer()
        self._create_native_window()

    def _setup_high_res_timer(self) -> None:
        if os.name == "nt":
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
                self._timer_period_set = True
            except Exception:
                pass

    def _create_native_window(self) -> None:
        if os.name != "nt":
            return
        ex_style = (
            WS_EX_LAYERED
            | WS_EX_TRANSPARENT
            | WS_EX_TOOLWINDOW
            | WS_EX_NOACTIVATE
            | WS_EX_TOPMOST
        )
        self._hwnd = _user32.CreateWindowExW(
            ex_style,
            "STATIC",
            "",
            WS_POPUP,
            0,
            0,
            1,
            1,
            0,
            0,
            0,
            0,
        )

    def flash(self, text: str, cfg: dict[str, Any]) -> None:
        if not text:
            return

        if self._hide_after_id is not None:
            try:
                self.root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None

        font_key = cfg.get("font_family", DEFAULT_FONT_KEY)
        font_size = int(cfg.get("font_size", 42))
        text_color = cfg.get("text_color", "#FFFFFF")
        bg_style = cfg.get("bg_style", "pill")
        opacity = max(0.05, min(1.0, float(cfg.get("opacity", 0.80))))
        position = cfg.get("position", "center")
        duration_ms = max(5, int(cfg.get("duration_ms", 35)))

        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        max_w = int(screen_w * 0.78)

        img = render_message_rgba(text, font_key, font_size, text_color, bg_style, max_w)
        w, h = img.size
        x, y = self._compute_position(position, screen_w, screen_h, w, h)

        if os.name == "nt" and self._hwnd:
            self._blit_layered(img, x, y, int(round(opacity * 255)))
            _user32.SetWindowPos(
                self._hwnd,
                HWND_TOPMOST,
                x,
                y,
                w,
                h,
                SWP_NOACTIVATE | SWP_SHOWWINDOW,
            )

        self._hide_after_id = self.root.after(duration_ms, self.hide)

    def _blit_layered(self, img: Image.Image, x: int, y: int, master_alpha: int) -> bool:
        w, h = img.size
        bgra = _rgba_to_premultiplied_bgra(img)

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = w
        bmi.bmiHeader.biHeight = -h  # top-down DIB
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = BI_RGB

        screen_dc = _user32.GetDC(0)
        mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
        bits_ptr = ctypes.c_void_p()
        hbmp = _gdi32.CreateDIBSection(
            screen_dc,
            ctypes.byref(bmi),
            DIB_RGB_COLORS,
            ctypes.byref(bits_ptr),
            None,
            0,
        )
        old_bmp = None
        ok = False
        try:
            if hbmp and bits_ptr.value:
                ctypes.memmove(bits_ptr.value, bgra, len(bgra))
                old_bmp = _gdi32.SelectObject(mem_dc, hbmp)
                pt_dst = POINT(x, y)
                sz = SIZE(w, h)
                pt_src = POINT(0, 0)
                blend = BLENDFUNCTION(AC_SRC_OVER, 0, master_alpha, AC_SRC_ALPHA)
                ok = bool(
                    _user32.UpdateLayeredWindow(
                        self._hwnd,
                        screen_dc,
                        ctypes.byref(pt_dst),
                        ctypes.byref(sz),
                        mem_dc,
                        ctypes.byref(pt_src),
                        0,
                        ctypes.byref(blend),
                        ULW_ALPHA,
                    )
                )
        finally:
            if old_bmp:
                _gdi32.SelectObject(mem_dc, old_bmp)
            if hbmp:
                _gdi32.DeleteObject(hbmp)
            if mem_dc:
                _gdi32.DeleteDC(mem_dc)
            if screen_dc:
                _user32.ReleaseDC(0, screen_dc)
        return ok

    def _compute_position(
        self, mode: str, screen_w: int, screen_h: int, w: int, h: int
    ) -> tuple[int, int]:
        margin_x = 40
        margin_y = 60
        max_x = max(margin_x, screen_w - w - margin_x)
        max_y = max(margin_y, screen_h - h - margin_y)

        if mode == "top":
            return max(0, (screen_w - w) // 2), min(max_y, int(screen_h * 0.14))
        if mode == "bottom":
            return max(0, (screen_w - w) // 2), max(margin_y, int(screen_h * 0.78) - h // 2)
        if mode == "random":
            return random.randint(margin_x, max_x), random.randint(margin_y, max_y)
        return max(0, (screen_w - w) // 2), max(0, (screen_h - h) // 2)

    def hide(self) -> None:
        self._hide_after_id = None
        if os.name == "nt" and self._hwnd:
            try:
                _user32.ShowWindow(self._hwnd, SW_HIDE)
            except Exception:
                pass

    def destroy(self) -> None:
        if self._hide_after_id is not None:
            try:
                self.root.after_cancel(self._hide_after_id)
            except Exception:
                pass
            self._hide_after_id = None
        if self._timer_period_set and os.name == "nt":
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
            self._timer_period_set = False
        if os.name == "nt" and self._hwnd:
            try:
                _user32.DestroyWindow(self._hwnd)
            except Exception:
                pass
            self._hwnd = 0
