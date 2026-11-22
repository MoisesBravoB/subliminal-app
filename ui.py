import ctypes
import os
import random
import tkinter as tk
from tkinter import colorchooser, filedialog, font as tkfont, messagebox, simpledialog, ttk
from typing import Any
import uuid

from PIL import Image, ImageTk

from catalog import CATALOG, CUSTOM_CATEGORY_KEY, get_category_messages, get_category_names
from config import (
    ICON_PATH,
    MAX_DURATION_MS,
    MIN_DURATION_MS,
    get_active_session,
    is_windows_autostart_enabled,
    load_config,
    save_config,
    set_windows_autostart,
)
from overlay import DEFAULT_FONT_KEY, RECOMMENDED_FONTS, SubliminalOverlay, render_preview_image
from tray import TrayManager

# Nintendo NES Minimalist Gray + Apple Palette
BG_MAIN = "#E4E3DF"         # Classic NES light warm gray shell
BG_HEADER = "#262628"       # NES charcoal bezel
BG_CARD = "#F4F3EF"         # Elevated minimalist silver-white panel
BG_INPUT = "#FFFFFF"        # Clean recessed white input/list
BG_TRACK = "#D5D3CC"        # Recessed hardware track
BORDER = "#C8C6BE"          # Crisp 1px hardware border
BORDER_DARK = "#3E3E42"     # Subtle border on dark header

TEXT_PRIMARY = "#1D1D1F"    # Apple graphite
TEXT_MUTED = "#6E6E73"      # Apple secondary gray
TEXT_ON_DARK = "#F5F5F7"    # Apple light on dark
TEXT_MUTED_DARK = "#A1A1A6"

NES_RED = "#D62828"         # Iconic NES button red
NES_RED_HOVER = "#B51E1E"
BTN_DARK = "#363639"        # NES controller dark gray
BTN_DARK_HOVER = "#1F1F21"
BTN_LIGHT = "#DFDDD7"       # Tactile light gray button
BTN_LIGHT_HOVER = "#CECCC5"
DANGER = "#B91C1C"
DANGER_HOVER = "#991B1B"

LED_GREEN = "#22C55E"
LED_AMBER = "#F59E0B"
LED_RED = "#EF4444"
LED_GRAY = "#8E8E93"

POSITION_LABELS = {
    "center": "Centro",
    "random": "Aleatoria",
    "top": "Superior",
    "bottom": "Inferior",
}
LABEL_TO_POSITION = {v: k for k, v in POSITION_LABELS.items()}
DAY_SHORT = ["L", "M", "X", "J", "V", "S", "D"]
MS_PRESETS = [5, 15, 35, 80, 200]


def _pick_apple_font(root: tk.Tk) -> str:
    available = set(tkfont.families(root))
    for candidate in (
        "SF Pro Display",
        "SF Pro Text",
        "Helvetica Neue",
        "Inter",
        "Segoe UI Variable Display",
        "Segoe UI",
        "Arial",
    ):
        if candidate in available:
            return candidate
    return "Segoe UI"


class SubliminalApp:
    def __init__(self, start_minimized_arg: bool = False):
        self.cfg: dict[str, Any] = load_config()
        self.cfg["auto_start"] = is_windows_autostart_enabled()

        self.root = tk.Tk()
        self.root.title("Subliminal Flash")
        self.root.configure(bg=BG_MAIN)
        self.root.geometry("980x760")
        self.root.minsize(900, 690)
        self._preview_photo = None

        self.font_ui = _pick_apple_font(self.root)
        self._window_icon_photo = None
        self._hicon_big = None
        self._hicon_small = None
        self._apply_window_icon()

        self._seq_index = 0
        self._flash_after_id: str | None = None
        self._status_after_id: str | None = None
        self._is_quitting = False
        self._active_tab = 0
        self._tab_frames: list[tk.Frame] = []
        self._tab_buttons: list[tuple[tk.Button, tk.Frame]] = []

        self.overlay = SubliminalOverlay(self.root)
        self.tray = TrayManager(
            on_open=lambda: self.root.after(0, self.show_window),
            on_toggle=lambda: self.root.after(0, self.toggle_enabled),
            on_test=lambda: self.root.after(0, self.test_flash),
            on_quit=lambda: self.root.after(0, self.quit_app),
            get_enabled=lambda: bool(self.cfg.get("enabled", True)),
        )

        self._setup_styles()
        self._build_ui()
        self._load_ui_from_config()

        self.root.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self.tray.start()

        if start_minimized_arg or self.cfg.get("start_minimized", False):
            self.root.withdraw()

        self._schedule_next_flash()
        self._poll_session_status()

    def _f(self, size: int, weight: str = "normal") -> tuple:
        return (self.font_ui, size, weight)

    def _apply_window_icon(self) -> None:
        if not ICON_PATH.exists():
            return
        try:
            self.root.iconbitmap(default=str(ICON_PATH))
        except Exception:
            pass
        try:
            ico_img = Image.open(ICON_PATH).convert("RGBA")
            self._window_icon_photo = ImageTk.PhotoImage(ico_img)
            self.root.iconphoto(True, self._window_icon_photo)
        except Exception:
            pass
        if os.name == "nt":
            self.root.after(50, self._apply_win32_taskbar_icon)

    def _apply_win32_taskbar_icon(self) -> None:
        if os.name != "nt" or not ICON_PATH.exists():
            return
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.root.winfo_id()) or self.root.winfo_id()
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x0010
            LR_DEFAULTSIZE = 0x0040
            WM_SETICON = 0x0080
            ICON_SMALL = 0
            ICON_BIG = 1

            user32.LoadImageW.restype = ctypes.c_void_p
            user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
            if not self._hicon_big:
                self._hicon_big = user32.LoadImageW(0, str(ICON_PATH), IMAGE_ICON, 48, 48, LR_LOADFROMFILE | LR_DEFAULTSIZE)
            if not self._hicon_small:
                self._hicon_small = user32.LoadImageW(0, str(ICON_PATH), IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
            if self._hicon_big:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, self._hicon_big)
            if self._hicon_small:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, self._hicon_small)
        except Exception:
            pass

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure(
            "NES.TCombobox",
            fieldbackground=BG_INPUT,
            background=BTN_LIGHT,
            foreground=TEXT_PRIMARY,
            bordercolor=BORDER,
            arrowcolor=TEXT_PRIMARY,
            padding=4,
        )
        style.map(
            "NES.TCombobox",
            fieldbackground=[("readonly", BG_INPUT)],
            foreground=[("readonly", TEXT_PRIMARY)],
            selectbackground=[("readonly", BG_HEADER)],
            selectforeground=[("readonly", TEXT_ON_DARK)],
        )

        style.configure(
            "NES.Horizontal.TScale",
            background=BG_CARD,
            troughcolor=BG_TRACK,
            sliderlength=16,
            borderwidth=0,
        )

        style.configure(
            "NES.Treeview",
            background=BG_INPUT,
            fieldbackground=BG_INPUT,
            foreground=TEXT_PRIMARY,
            rowheight=30,
            borderwidth=0,
            font=self._f(9),
        )
        style.configure(
            "NES.Treeview.Heading",
            background=BG_TRACK,
            foreground=TEXT_PRIMARY,
            font=self._f(9, "bold"),
            relief="flat",
            padding=(6, 6),
        )
        style.map(
            "NES.Treeview",
            background=[("selected", BG_HEADER)],
            foreground=[("selected", TEXT_ON_DARK)],
        )

    def _build_ui(self) -> None:
        # =====================================================================
        # NES CHARCOAL CONSOLE HEADER + RED STRIPE
        # =====================================================================
        header_wrap = tk.Frame(self.root, bg=BG_HEADER)
        header_wrap.pack(fill="x")

        header = tk.Frame(header_wrap, bg=BG_HEADER, padx=22, pady=14)
        header.pack(fill="x")

        # Left branding + LED status
        brand_col = tk.Frame(header, bg=BG_HEADER)
        brand_col.pack(side="left")

        title_row = tk.Frame(brand_col, bg=BG_HEADER)
        title_row.pack(anchor="w")

        tk.Label(
            title_row,
            text="Subliminal Flash",
            font=self._f(16, "bold"),
            fg=TEXT_ON_DARK,
            bg=BG_HEADER,
        ).pack(side="left")

        self.status_badge = tk.Label(
            title_row,
            text="● ACTIVO",
            font=self._f(8, "bold"),
            fg=LED_GREEN,
            bg="#1A1A1C",
            padx=10,
            pady=4,
            highlightbackground=BORDER_DARK,
            highlightthickness=1,
        )
        self.status_badge.pack(side="left", padx=(14, 0))

        tk.Label(
            brand_col,
            text="SUBLIMINAL SYSTEM  •  EDICIÓN MINIMALISTA",
            font=self._f(7, "bold"),
            fg=TEXT_MUTED_DARK,
            bg=BG_HEADER,
        ).pack(anchor="w", pady=(2, 0))

        # Right console action buttons
        btn_box = tk.Frame(header, bg=BG_HEADER)
        btn_box.pack(side="right")

        self.btn_toggle = self._make_button(
            btn_box, "Pausar", self.toggle_enabled, bg=NES_RED, hover=NES_RED_HOVER, fg=TEXT_ON_DARK, padx=16, pady=7
        )
        self.btn_toggle.pack(side="left", padx=(0, 8))

        self.btn_test = self._make_button(
            btn_box, "Probar ahora", self.test_flash, bg=BTN_DARK, hover="#454549", fg=TEXT_ON_DARK, padx=14, pady=7
        )
        self.btn_test.pack(side="left", padx=(0, 8))

        self.btn_bg = self._make_button(
            btn_box, "Segundo plano", self.hide_to_tray, bg=BTN_DARK, hover="#454549", fg=TEXT_ON_DARK, padx=14, pady=7
        )
        self.btn_bg.pack(side="left")

        # Iconic 3px NES red stripe under console bar
        tk.Frame(header_wrap, bg=NES_RED, height=3).pack(fill="x")

        # =====================================================================
        # APPLE / NES SEGMENTED TAB BAR
        # =====================================================================
        nav_outer = tk.Frame(self.root, bg=BG_MAIN, padx=20, pady=12)
        nav_outer.pack(fill="x")

        seg_track = tk.Frame(nav_outer, bg=BG_TRACK, padx=4, pady=4, highlightbackground=BORDER, highlightthickness=1)
        seg_track.pack(fill="x")

        tabs_meta = [
            ("Inicio y Mensajes", 0),
            ("Catálogo por Categorías", 1),
            ("Sesiones Programadas", 2),
        ]
        for col_idx, (label, tab_idx) in enumerate(tabs_meta):
            seg_track.columnconfigure(col_idx, weight=1)
            cell = tk.Frame(seg_track, bg=BG_TRACK)
            cell.grid(row=0, column=col_idx, sticky="ew", padx=2)

            btn = tk.Button(
                cell,
                text=label,
                command=lambda idx=tab_idx: self._select_tab(idx),
                font=self._f(9, "bold"),
                relief="flat",
                borderwidth=0,
                pady=7,
                cursor="hand2",
            )
            btn.pack(fill="x")
            indicator = tk.Frame(cell, height=2, bg=BG_TRACK)
            indicator.pack(fill="x")
            self._tab_buttons.append((btn, indicator))

        # =====================================================================
        # MINIMALIST FOOTER BAR (packed bottom first so it never clips at high DPI)
        # =====================================================================
        footer = tk.Frame(self.root, bg=BG_MAIN, padx=20, pady=8)
        footer.pack(side="bottom", fill="x")

        tk.Label(
            footer,
            text="Al cerrar esta ventana la app sigue activa en segundo plano (ícono en la bandeja del sistema).",
            font=self._f(8),
            fg=TEXT_MUTED,
            bg=BG_MAIN,
        ).pack(side="left")

        self._make_button(
            footer,
            "Salir por completo",
            self.quit_app,
            bg=BTN_LIGHT,
            hover="#D4B8B8",
            fg=DANGER,
            padx=12,
            pady=4,
        ).pack(side="right")

        # =====================================================================
        # TAB CONTENT STACK
        # =====================================================================
        self.content_stack = tk.Frame(self.root, bg=BG_MAIN)
        self.content_stack.pack(fill="both", expand=True, padx=20, pady=(0, 4))

        tab_main = tk.Frame(self.content_stack, bg=BG_MAIN)
        tab_catalog = tk.Frame(self.content_stack, bg=BG_MAIN)
        tab_sessions = tk.Frame(self.content_stack, bg=BG_MAIN)
        self._tab_frames = [tab_main, tab_catalog, tab_sessions]

        self._build_main_tab(tab_main)
        self._build_catalog_tab(tab_catalog)
        self._build_sessions_tab(tab_sessions)

        self._select_tab(0)

    def _select_tab(self, index: int) -> None:
        self._active_tab = index
        for i, frame in enumerate(self._tab_frames):
            if i == index:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()

        for i, (btn, indicator) in enumerate(self._tab_buttons):
            if i == index:
                btn.configure(bg=BG_INPUT, fg=TEXT_PRIMARY, activebackground=BG_INPUT, activeforeground=TEXT_PRIMARY)
                indicator.configure(bg=NES_RED)
            else:
                btn.configure(bg=BG_TRACK, fg=TEXT_MUTED, activebackground="#CCCAC2", activeforeground=TEXT_PRIMARY)
                indicator.configure(bg=BG_TRACK)

    # =========================================================================
    # TAB 1: INICIO Y MENSAJES
    # =========================================================================
    def _build_main_tab(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg=BG_MAIN)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=5)
        body.columnconfigure(1, weight=5)
        body.rowconfigure(0, weight=1)

        # LEFT COLUMN: Messages
        left_card = self._make_card(body, "MIS MENSAJES")
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        add_row = tk.Frame(left_card, bg=BG_CARD)
        add_row.pack(fill="x", pady=(0, 10))

        self.msg_entry = tk.Entry(
            add_row,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(10),
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=NES_RED,
        )
        self.msg_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))
        self.msg_entry.bind("<Return>", lambda e: self.add_message())

        self._make_button(add_row, "Agregar", self.add_message, bg=NES_RED, hover=NES_RED_HOVER, fg=TEXT_ON_DARK).pack(side="right")

        list_frame = tk.Frame(left_card, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill="both", expand=True)

        self.msg_listbox = tk.Listbox(
            list_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            selectbackground=BG_HEADER,
            selectforeground=TEXT_ON_DARK,
            font=self._f(10),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
        )
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.msg_listbox.yview)
        self.msg_listbox.configure(yscrollcommand=scrollbar.set)
        self.msg_listbox.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        scrollbar.pack(side="right", fill="y")
        self.msg_listbox.bind("<Double-Button-1>", lambda e: self.edit_message())
        self.msg_listbox.bind("<<ListboxSelect>>", lambda e: self._update_preview())

        msg_actions = tk.Frame(left_card, bg=BG_CARD)
        msg_actions.pack(fill="x", pady=(10, 8))

        self._make_button(msg_actions, "Editar", self.edit_message, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY).pack(side="left", padx=(0, 6))
        self._make_button(msg_actions, "Eliminar", self.delete_message, bg=BTN_LIGHT, hover="#E2C4C4", fg=DANGER).pack(side="left", padx=(0, 6))
        self._make_button(msg_actions, "Importar .txt", self.import_messages, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY).pack(side="right")
        self._make_button(msg_actions, "Exportar", self.export_messages, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY).pack(side="right", padx=(0, 6))

        order_row = tk.Frame(left_card, bg=BG_CARD)
        order_row.pack(fill="x")
        tk.Label(order_row, text="Orden:", font=self._f(9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        self.order_var = tk.StringVar(value="random")
        for val, lbl in (("random", "Aleatorio"), ("sequential", "Secuencial")):
            tk.Radiobutton(
                order_row,
                text=lbl,
                variable=self.order_var,
                value=val,
                command=self._on_setting_changed,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=TEXT_PRIMARY,
                font=self._f(9),
            ).pack(side="left", padx=(10, 0))

        self.msg_count_label = tk.Label(order_row, text="0 mensajes", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD)
        self.msg_count_label.pack(side="right")

        # RIGHT COLUMN: Timing + Appearance + System
        right_col = tk.Frame(body, bg=BG_MAIN)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Card 1: Timing
        timing_card = self._make_card(right_col, "TEMPORIZACIÓN")
        timing_card.pack(fill="x", pady=(0, 10))

        dur_top = tk.Frame(timing_card, bg=BG_CARD)
        dur_top.pack(fill="x")

        tk.Label(dur_top, text="Duración en pantalla", font=self._f(9, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD).pack(side="left")
        self.dur_hint_label = tk.Label(dur_top, text="Subliminal", font=self._f(8, "bold"), fg=NES_RED, bg=BG_CARD)
        self.dur_hint_label.pack(side="right")

        dur_ctrl = tk.Frame(timing_card, bg=BG_CARD)
        dur_ctrl.pack(fill="x", pady=(6, 8))

        self.duration_var = tk.IntVar(value=35)
        self.duration_scale = ttk.Scale(
            dur_ctrl,
            from_=MIN_DURATION_MS,
            to=500,
            orient="horizontal",
            style="NES.Horizontal.TScale",
            command=self._on_duration_scale,
        )
        self.duration_scale.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.duration_spin = tk.Spinbox(
            dur_ctrl,
            from_=MIN_DURATION_MS,
            to=MAX_DURATION_MS,
            increment=5,
            textvariable=self.duration_var,
            width=6,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            buttonbackground=BTN_LIGHT,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            font=self._f(10, "bold"),
            command=self._on_duration_spin,
        )
        self.duration_spin.pack(side="right")
        self.duration_spin.bind("<KeyRelease>", lambda e: self._on_duration_spin())
        self.duration_spin.bind("<FocusOut>", lambda e: self._on_duration_spin())

        tk.Label(dur_ctrl, text="ms", font=self._f(9, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="right", padx=(0, 4))

        # Quick ms tactile presets
        preset_row = tk.Frame(timing_card, bg=BG_CARD)
        preset_row.pack(fill="x", pady=(0, 10))
        tk.Label(preset_row, text="Rápido:", font=self._f(8), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left", padx=(0, 6))
        for ms_val in MS_PRESETS:
            self._make_button(
                preset_row,
                f"{ms_val} ms",
                lambda v=ms_val: self._apply_ms_preset(v),
                bg=BTN_LIGHT,
                hover=BTN_LIGHT_HOVER,
                fg=TEXT_PRIMARY,
                padx=8,
                pady=2,
            ).pack(side="left", padx=(0, 5))

        # Interval row
        int_inputs = tk.Frame(timing_card, bg=BG_CARD)
        int_inputs.pack(fill="x", pady=(2, 0))

        tk.Label(int_inputs, text="Intervalo (seg):", font=self._f(9, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD).pack(side="left")

        tk.Label(int_inputs, text="Mín", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left", padx=(10, 4))
        self.min_s_var = tk.DoubleVar(value=5.0)
        self.min_s_spin = tk.Spinbox(
            int_inputs,
            from_=0.5,
            to=3600.0,
            increment=1.0,
            textvariable=self.min_s_var,
            width=6,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            buttonbackground=BTN_LIGHT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            font=self._f(9),
            command=self._on_setting_changed,
        )
        self.min_s_spin.pack(side="left", padx=(0, 12))
        self.min_s_spin.bind("<FocusOut>", lambda e: self._on_setting_changed())
        self.min_s_spin.bind("<Return>", lambda e: self._on_setting_changed())

        tk.Label(int_inputs, text="Máx", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left", padx=(0, 4))
        self.max_s_var = tk.DoubleVar(value=12.0)
        self.max_s_spin = tk.Spinbox(
            int_inputs,
            from_=0.5,
            to=3600.0,
            increment=1.0,
            textvariable=self.max_s_var,
            width=6,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            buttonbackground=BTN_LIGHT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            font=self._f(9),
            command=self._on_setting_changed,
        )
        self.max_s_spin.pack(side="left")
        self.max_s_spin.bind("<FocusOut>", lambda e: self._on_setting_changed())
        self.max_s_spin.bind("<Return>", lambda e: self._on_setting_changed())

        # Card 2: Appearance + Live Preview
        app_card = self._make_card(right_col, "APARIENCIA Y VISTA PREVIA")
        app_card.pack(fill="x", pady=(0, 10))

        # Live WYSIWYG Preview Box
        preview_wrap = tk.Frame(app_card, bg="#34363A", highlightbackground=BORDER, highlightthickness=1)
        preview_wrap.pack(fill="x", pady=(0, 10))
        self.preview_label = tk.Label(preview_wrap, bg="#34363A", borderwidth=0)
        self.preview_label.pack(fill="x")

        # Font selector row
        row_font = tk.Frame(app_card, bg=BG_CARD)
        row_font.pack(fill="x", pady=(0, 8))

        tk.Label(row_font, text="Fuente:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.font_var = tk.StringVar(value=DEFAULT_FONT_KEY)
        self.font_combo = ttk.Combobox(
            row_font,
            textvariable=self.font_var,
            values=list(RECOMMENDED_FONTS.keys()),
            state="readonly",
            style="NES.TCombobox",
            width=24,
        )
        self.font_combo.pack(side="left", padx=(8, 14))
        self.font_combo.bind("<<ComboboxSelected>>", lambda e: self._on_setting_changed())

        tk.Label(row_font, text="Tamaño:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.font_size_var = tk.IntVar(value=42)
        self.font_spin = tk.Spinbox(
            row_font,
            from_=14,
            to=120,
            increment=2,
            textvariable=self.font_size_var,
            width=5,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            buttonbackground=BTN_LIGHT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            font=self._f(9),
            command=self._on_setting_changed,
        )
        self.font_spin.pack(side="left", padx=(6, 0))
        self.font_spin.bind("<KeyRelease>", lambda e: self._on_setting_changed())
        self.font_spin.bind("<FocusOut>", lambda e: self._on_setting_changed())
        self.font_spin.bind("<Return>", lambda e: self._on_setting_changed())

        row1 = tk.Frame(app_card, bg=BG_CARD)
        row1.pack(fill="x", pady=(0, 8))

        tk.Label(row1, text="Posición:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.pos_var = tk.StringVar(value="Centro")
        self.pos_combo = ttk.Combobox(
            row1,
            textvariable=self.pos_var,
            values=list(POSITION_LABELS.values()),
            state="readonly",
            style="NES.TCombobox",
            width=12,
        )
        self.pos_combo.pack(side="left", padx=(8, 16))
        self.pos_combo.bind("<<ComboboxSelected>>", lambda e: self._on_setting_changed())

        tk.Label(row1, text="Color:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.color_preview = tk.Label(row1, text="   ", bg="#FFFFFF", highlightbackground=BORDER, highlightthickness=1)
        self.color_preview.pack(side="left", padx=(6, 6))
        self._make_button(row1, "Elegir color", self.pick_color, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY, pady=3).pack(side="left")

        row2 = tk.Frame(app_card, bg=BG_CARD)
        row2.pack(fill="x", pady=(0, 8))

        tk.Label(row2, text="Opacidad:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.opacity_var = tk.DoubleVar(value=0.80)
        self.opacity_scale = ttk.Scale(
            row2,
            from_=10,
            to=100,
            orient="horizontal",
            style="NES.Horizontal.TScale",
            command=self._on_opacity_scale,
        )
        self.opacity_scale.pack(side="left", fill="x", expand=True, padx=(10, 10))
        self.opacity_pct_label = tk.Label(row2, text="80%", font=self._f(9, "bold"), fg=TEXT_PRIMARY, bg=BG_CARD, width=5)
        self.opacity_pct_label.pack(side="right")

        row4 = tk.Frame(app_card, bg=BG_CARD)
        row4.pack(fill="x")
        tk.Label(row4, text="Fondo:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.bg_style_var = tk.StringVar(value="pill")
        for val, lbl in (("transparent", "Sin fondo (flotante)"), ("pill", "Cápsula oscura")):
            tk.Radiobutton(
                row4,
                text=lbl,
                variable=self.bg_style_var,
                value=val,
                command=self._on_setting_changed,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=TEXT_PRIMARY,
                font=self._f(9),
            ).pack(side="left", padx=(10, 0))

        # Card 3: System
        sys_card = self._make_card(right_col, "SISTEMA")
        sys_card.pack(fill="x")

        self.start_min_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            sys_card,
            text="Iniciar minimizado en la bandeja del sistema",
            variable=self.start_min_var,
            command=self._on_setting_changed,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            selectcolor=BG_INPUT,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            font=self._f(9),
        ).pack(anchor="w")

        self.autostart_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            sys_card,
            text="Iniciar automáticamente con Windows",
            variable=self.autostart_var,
            command=self._on_autostart_toggled,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            selectcolor=BG_INPUT,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            font=self._f(9),
        ).pack(anchor="w", pady=(3, 0))

    # =========================================================================
    # TAB 2: CATÁLOGO POR CATEGORÍAS
    # =========================================================================
    def _build_catalog_tab(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg=BG_MAIN)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=4)
        body.columnconfigure(1, weight=6)
        body.rowconfigure(0, weight=1)

        cat_card = self._make_card(body, "CATEGORÍAS")
        cat_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        cat_list_frame = tk.Frame(cat_card, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
        cat_list_frame.pack(fill="both", expand=True)

        self.cat_listbox = tk.Listbox(
            cat_list_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            selectbackground=BG_HEADER,
            selectforeground=TEXT_ON_DARK,
            font=self._f(10, "bold"),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            exportselection=False,
        )
        self.cat_listbox.pack(fill="both", expand=True, padx=8, pady=8)
        for name in get_category_names():
            count = len(CATALOG[name])
            self.cat_listbox.insert(tk.END, f"{name}  ({count})")
        self.cat_listbox.bind("<<ListboxSelect>>", self._on_catalog_category_selected)

        prev_card = self._make_card(body, "MENSAJES DE LA CATEGORÍA")
        prev_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        tk.Label(
            prev_card,
            text="Selecciona uno o varios mensajes (Ctrl/Shift + clic) o agrega toda la categoría:",
            font=self._f(9),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 8))

        prev_frame = tk.Frame(prev_card, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
        prev_frame.pack(fill="both", expand=True)

        self.cat_msg_listbox = tk.Listbox(
            prev_frame,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            selectbackground=BG_HEADER,
            selectforeground=TEXT_ON_DARK,
            font=self._f(10),
            borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            selectmode="extended",
        )
        cat_scroll = tk.Scrollbar(prev_frame, orient="vertical", command=self.cat_msg_listbox.yview)
        self.cat_msg_listbox.configure(yscrollcommand=cat_scroll.set)
        self.cat_msg_listbox.pack(side="left", fill="both", expand=True, padx=8, pady=8)
        cat_scroll.pack(side="right", fill="y")

        act1 = tk.Frame(prev_card, bg=BG_CARD)
        act1.pack(fill="x", pady=(10, 6))
        self._make_button(act1, "Agregar seleccionados", self.add_selected_catalog_msgs, bg=NES_RED, hover=NES_RED_HOVER, fg=TEXT_ON_DARK).pack(side="left", padx=(0, 8))
        self._make_button(act1, "Agregar toda la categoría", self.add_all_catalog_msgs, bg=BTN_DARK, hover=BTN_DARK_HOVER, fg=TEXT_ON_DARK).pack(side="left", padx=(0, 8))
        self._make_button(act1, "Reemplazar Mis mensajes", self.replace_with_catalog, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY).pack(side="left")

        act2 = tk.Frame(prev_card, bg=BG_CARD)
        act2.pack(fill="x")
        self._make_button(
            act2,
            "Programar sesión con esta categoría →",
            self.send_category_to_session,
            bg=BTN_LIGHT,
            hover=BTN_LIGHT_HOVER,
            fg=TEXT_PRIMARY,
        ).pack(side="left")

        self.cat_listbox.selection_set(0)
        self._on_catalog_category_selected()

    # =========================================================================
    # TAB 3: SESIONES PROGRAMADAS
    # =========================================================================
    def _build_sessions_tab(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg=BG_MAIN)
        body.pack(fill="both", expand=True)

        list_card = self._make_card(body, "SESIONES PROGRAMADAS")
        list_card.pack(fill="both", expand=True, pady=(0, 10))

        top_opts = tk.Frame(list_card, bg=BG_CARD)
        top_opts.pack(fill="x", pady=(0, 8))

        self.sessions_only_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            top_opts,
            text="Solo mostrar destellos durante sesiones programadas (pausar fuera de horario)",
            variable=self.sessions_only_var,
            command=self._on_setting_changed,
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            selectcolor=BG_INPUT,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            font=self._f(9),
        ).pack(side="left")

        tree_frame = tk.Frame(list_card, bg=BG_INPUT, highlightbackground=BORDER, highlightthickness=1)
        tree_frame.pack(fill="both", expand=True)

        cols = ("estado", "nombre", "categoria", "horario", "dias", "ms")
        self.sessions_tree = ttk.Treeview(
            tree_frame,
            columns=cols,
            show="headings",
            style="NES.Treeview",
            selectmode="browse",
        )
        self.sessions_tree.heading("estado", text="Estado")
        self.sessions_tree.heading("nombre", text="Nombre")
        self.sessions_tree.heading("categoria", text="Categoría")
        self.sessions_tree.heading("horario", text="Horario")
        self.sessions_tree.heading("dias", text="Días")
        self.sessions_tree.heading("ms", text="Duración")

        self.sessions_tree.column("estado", width=95, anchor="center")
        self.sessions_tree.column("nombre", width=165, anchor="w")
        self.sessions_tree.column("categoria", width=190, anchor="w")
        self.sessions_tree.column("horario", width=115, anchor="center")
        self.sessions_tree.column("dias", width=140, anchor="center")
        self.sessions_tree.column("ms", width=85, anchor="center")

        tscroll = tk.Scrollbar(tree_frame, orient="vertical", command=self.sessions_tree.yview)
        self.sessions_tree.configure(yscrollcommand=tscroll.set)
        self.sessions_tree.pack(side="left", fill="both", expand=True)
        tscroll.pack(side="right", fill="y")

        sess_btns = tk.Frame(list_card, bg=BG_CARD)
        sess_btns.pack(fill="x", pady=(8, 0))
        self._make_button(sess_btns, "Activar / Pausar sesión", self.toggle_selected_session, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY).pack(side="left", padx=(0, 8))
        self._make_button(sess_btns, "Eliminar sesión", self.delete_selected_session, bg=BTN_LIGHT, hover="#E2C4C4", fg=DANGER).pack(side="left")

        # Bottom card: create new session
        form_card = self._make_card(body, "NUEVA SESIÓN")
        form_card.pack(fill="x")

        r1 = tk.Frame(form_card, bg=BG_CARD)
        r1.pack(fill="x", pady=(0, 8))

        tk.Label(r1, text="Nombre:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.sess_name_var = tk.StringVar(value="Sesión de enfoque")
        tk.Entry(
            r1,
            textvariable=self.sess_name_var,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(9),
            width=24,
            highlightthickness=1,
            highlightbackground=BORDER,
        ).pack(side="left", padx=(6, 16), ipady=4)

        tk.Label(r1, text="Categoría:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.sess_cat_var = tk.StringVar(value=get_category_names()[0])
        self.sess_cat_combo = ttk.Combobox(
            r1,
            textvariable=self.sess_cat_var,
            values=get_category_names() + [CUSTOM_CATEGORY_KEY],
            state="readonly",
            style="NES.TCombobox",
            width=26,
        )
        self.sess_cat_combo.pack(side="left", padx=(6, 0))

        r2 = tk.Frame(form_card, bg=BG_CARD)
        r2.pack(fill="x", pady=(0, 8))

        tk.Label(r2, text="Inicio (HH:MM):", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.sess_start_var = tk.StringVar(value="09:00")
        tk.Entry(
            r2,
            textvariable=self.sess_start_var,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(9),
            width=8,
            highlightthickness=1,
            highlightbackground=BORDER,
        ).pack(side="left", padx=(6, 14), ipady=4)

        tk.Label(r2, text="Fin (HH:MM):", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.sess_end_var = tk.StringVar(value="12:00")
        tk.Entry(
            r2,
            textvariable=self.sess_end_var,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(9),
            width=8,
            highlightthickness=1,
            highlightbackground=BORDER,
        ).pack(side="left", padx=(6, 14), ipady=4)

        tk.Label(r2, text="Duración (ms, opcional):", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")
        self.sess_ms_var = tk.StringVar(value="")
        tk.Entry(
            r2,
            textvariable=self.sess_ms_var,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(9),
            width=7,
            highlightthickness=1,
            highlightbackground=BORDER,
        ).pack(side="left", padx=(6, 6), ipady=4)
        tk.Label(r2, text=f"(mín {MIN_DURATION_MS} ms; vacío = global)", font=self._f(8), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        r3 = tk.Frame(form_card, bg=BG_CARD)
        r3.pack(fill="x")

        tk.Label(r3, text="Días:", font=self._f(9), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left", padx=(0, 6))
        self.sess_day_vars: list[tk.BooleanVar] = []
        for d_lbl in DAY_SHORT:
            var = tk.BooleanVar(value=True)
            self.sess_day_vars.append(var)
            tk.Checkbutton(
                r3,
                text=d_lbl,
                variable=var,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=TEXT_PRIMARY,
                font=self._f(9, "bold"),
            ).pack(side="left", padx=(0, 4))

        self._make_button(r3, "Guardar sesión", self.add_session, bg=NES_RED, hover=NES_RED_HOVER, fg=TEXT_ON_DARK).pack(side="right")

    # =========================================================================
    # UI COMPONENT FACTORIES
    # =========================================================================
    def _make_card(self, parent: tk.Widget, title: str) -> tk.Frame:
        outer = tk.Frame(parent, bg=BG_CARD, padx=16, pady=12, highlightbackground=BORDER, highlightthickness=1)
        hdr = tk.Frame(outer, bg=BG_CARD)
        hdr.pack(fill="x", pady=(0, 10))
        tk.Frame(hdr, bg=NES_RED, width=3, height=13).pack(side="left", padx=(0, 8))
        tk.Label(
            hdr,
            text=title,
            font=self._f(9, "bold"),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        ).pack(side="left")
        return outer

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command,
        bg: str = NES_RED,
        hover: str = NES_RED_HOVER,
        fg: str = TEXT_ON_DARK,
        padx: int = 12,
        pady: int = 5,
    ) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            font=self._f(9, "bold"),
            padx=padx,
            pady=pady,
            cursor="hand2",
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover))
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg))
        return btn

    # =========================================================================
    # STATE SYNC
    # =========================================================================
    def _load_ui_from_config(self) -> None:
        self._refresh_message_list()
        self._refresh_sessions_tree()
        self.order_var.set(self.cfg.get("order_mode", "random"))

        dur = int(self.cfg.get("duration_ms", 35))
        self.duration_var.set(dur)
        self.duration_scale.set(min(500, dur))
        self._update_duration_hint(dur)

        self.min_s_var.set(self.cfg.get("interval_min_s", 5.0))
        self.max_s_var.set(self.cfg.get("interval_max_s", 12.0))

        pos_key = self.cfg.get("position", "center")
        self.pos_var.set(POSITION_LABELS.get(pos_key, "Centro"))
        self.font_var.set(self.cfg.get("font_family", DEFAULT_FONT_KEY))
        self.font_size_var.set(int(self.cfg.get("font_size", 42)))

        op = float(self.cfg.get("opacity", 0.80))
        self.opacity_var.set(op)
        self.opacity_scale.set(int(op * 100))
        self.opacity_pct_label.configure(text=f"{int(op * 100)}%")

        self.color_preview.configure(bg=self.cfg.get("text_color", "#FFFFFF"))
        self.bg_style_var.set(self.cfg.get("bg_style", "pill"))

        self.start_min_var.set(bool(self.cfg.get("start_minimized", False)))
        self.autostart_var.set(bool(self.cfg.get("auto_start", False)))
        self.sessions_only_var.set(bool(self.cfg.get("sessions_only", False)))

        self._update_status_ui()
        self._update_preview()

    def _update_preview(self) -> None:
        try:
            sel = self.msg_listbox.curselection()
            if sel:
                sample = self.cfg["messages"][sel[0]]
            elif self.cfg.get("messages"):
                sample = self.cfg["messages"][0]
            else:
                sample = "Estoy enfocado y en calma"
            img = render_preview_image(sample, self.cfg, box_w=420, box_h=78)
            self._preview_photo = ImageTk.PhotoImage(img)
            self.preview_label.configure(image=self._preview_photo)
        except Exception:
            pass

    def _refresh_message_list(self) -> None:
        self.msg_listbox.delete(0, tk.END)
        for msg in self.cfg.get("messages", []):
            self.msg_listbox.insert(tk.END, msg)
        count = len(self.cfg.get("messages", []))
        self.msg_count_label.configure(text=f"{count} {'mensaje' if count == 1 else 'mensajes'}")

    def _refresh_sessions_tree(self) -> None:
        for item in self.sessions_tree.get_children():
            self.sessions_tree.delete(item)
        active_sess = get_active_session(self.cfg)
        active_id = active_sess["id"] if active_sess else None

        for s in self.cfg.get("sessions", []):
            if not s.get("enabled", True):
                estado = "Pausada"
            elif s["id"] == active_id:
                estado = "● En curso"
            else:
                estado = "Programada"
            horario = f"{s['start_time']} - {s['end_time']}"
            dias = " ".join(DAY_SHORT[d] for d in s.get("days", []))
            ms_str = f"{s['duration_ms']} ms" if s.get("duration_ms") is not None else "Global"
            self.sessions_tree.insert(
                "",
                tk.END,
                iid=s["id"],
                values=(estado, s["name"], s["category"], horario, dias, ms_str),
            )

    def _update_duration_hint(self, ms: int) -> None:
        if ms <= 20:
            self.dur_hint_label.configure(text="Extremo (subliminal puro)", fg=NES_RED)
        elif ms <= 50:
            self.dur_hint_label.configure(text="Ultra rápido (subliminal)", fg="#15803D")
        elif ms <= 150:
            self.dur_hint_label.configure(text="Rápido (semi-consciente)", fg="#B45309")
        else:
            self.dur_hint_label.configure(text="Visible (consciente)", fg=TEXT_MUTED)

    def _update_status_ui(self) -> None:
        enabled = bool(self.cfg.get("enabled", True))
        if not enabled:
            self.status_badge.configure(text="● PAUSADO", fg=LED_AMBER)
            self.btn_toggle.configure(text="Activar")
        else:
            active_sess = get_active_session(self.cfg)
            if active_sess:
                ms_val = active_sess.get("duration_ms") or self.cfg.get("duration_ms", 35)
                self.status_badge.configure(
                    text=f"● SESIÓN: {active_sess['name'].upper()} ({ms_val} ms)",
                    fg=LED_RED,
                )
            elif self.cfg.get("sessions_only", False):
                self.status_badge.configure(text="● ESPERANDO SESIÓN", fg=LED_GRAY)
            else:
                self.status_badge.configure(text="● ACTIVO", fg=LED_GREEN)
            self.btn_toggle.configure(text="Pausar")
        self.tray.update_state(enabled)

    def _poll_session_status(self) -> None:
        if self._is_quitting:
            return
        self._update_status_ui()
        self._refresh_sessions_tree()
        self._status_after_id = self.root.after(15000, self._poll_session_status)

    # =========================================================================
    # SETTINGS & MESSAGE HANDLERS
    # =========================================================================
    def _apply_ms_preset(self, ms: int) -> None:
        ms = max(MIN_DURATION_MS, min(MAX_DURATION_MS, ms))
        self.duration_var.set(ms)
        self.duration_scale.set(min(500, ms))
        self._update_duration_hint(ms)
        self.cfg["duration_ms"] = ms
        self.cfg = save_config(self.cfg)
        self._update_status_ui()

    def _on_duration_scale(self, val: str) -> None:
        ms = max(MIN_DURATION_MS, int(float(val)))
        self.duration_var.set(ms)
        self._update_duration_hint(ms)
        self.cfg["duration_ms"] = ms
        self.cfg = save_config(self.cfg)
        self._update_status_ui()

    def _on_duration_spin(self) -> None:
        try:
            ms = int(self.duration_spin.get())
        except ValueError:
            return
        ms = max(MIN_DURATION_MS, min(MAX_DURATION_MS, ms))
        self.duration_scale.set(min(500, ms))
        self._update_duration_hint(ms)
        self.cfg["duration_ms"] = ms
        self.cfg = save_config(self.cfg)
        self._update_status_ui()

    def _on_opacity_scale(self, val: str) -> None:
        pct = int(float(val))
        self.opacity_pct_label.configure(text=f"{pct}%")
        self.cfg["opacity"] = round(pct / 100.0, 2)
        self.cfg = save_config(self.cfg)
        self._update_preview()

    def _on_setting_changed(self) -> None:
        self.cfg["order_mode"] = self.order_var.get()
        self.cfg["font_family"] = self.font_var.get()
        try:
            self.cfg["interval_min_s"] = float(self.min_s_spin.get())
        except ValueError:
            pass
        try:
            self.cfg["interval_max_s"] = float(self.max_s_spin.get())
        except ValueError:
            pass
        self.cfg["position"] = LABEL_TO_POSITION.get(self.pos_var.get(), "center")
        try:
            self.cfg["font_size"] = int(self.font_spin.get())
        except ValueError:
            pass
        self.cfg["bg_style"] = self.bg_style_var.get()
        self.cfg["start_minimized"] = bool(self.start_min_var.get())
        self.cfg["sessions_only"] = bool(self.sessions_only_var.get())

        self.cfg = save_config(self.cfg)
        self.min_s_var.set(self.cfg["interval_min_s"])
        self.max_s_var.set(self.cfg["interval_max_s"])
        self._update_status_ui()
        self._update_preview()
        self._schedule_next_flash()

    def _on_autostart_toggled(self) -> None:
        want = bool(self.autostart_var.get())
        ok = set_windows_autostart(want)
        if not ok:
            messagebox.showwarning("Aviso", "No se pudo actualizar el inicio automático con Windows.")
            self.autostart_var.set(is_windows_autostart_enabled())
        self.cfg["auto_start"] = bool(self.autostart_var.get())
        self.cfg = save_config(self.cfg)

    def pick_color(self) -> None:
        chosen = colorchooser.askcolor(
            color=self.cfg.get("text_color", "#FFFFFF"),
            title="Elegir color del texto",
            parent=self.root,
        )
        if chosen and chosen[1]:
            self.cfg["text_color"] = chosen[1]
            self.color_preview.configure(bg=chosen[1])
            self.cfg = save_config(self.cfg)
            self._update_preview()

    def add_message(self) -> None:
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.cfg.setdefault("messages", []).append(text)
        self.cfg = save_config(self.cfg)
        self.msg_entry.delete(0, tk.END)
        self._refresh_message_list()
        self.msg_listbox.see(tk.END)

    def edit_message(self) -> None:
        sel = self.msg_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        current = self.cfg["messages"][idx]
        updated = simpledialog.askstring(
            "Editar mensaje",
            "Modifica tu mensaje subliminal:",
            initialvalue=current,
            parent=self.root,
        )
        if updated is not None and updated.strip():
            self.cfg["messages"][idx] = updated.strip()
            self.cfg = save_config(self.cfg)
            self._refresh_message_list()
            self.msg_listbox.selection_set(idx)

    def delete_message(self) -> None:
        sel = self.msg_listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        del self.cfg["messages"][idx]
        self.cfg = save_config(self.cfg)
        self._refresh_message_list()

    def import_messages(self) -> None:
        path = filedialog.askopenfilename(
            title="Importar mensajes desde archivo de texto",
            filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            if not lines:
                messagebox.showinfo("Importar", "El archivo no contiene mensajes.")
                return
            self.cfg["messages"].extend(lines)
            self.cfg = save_config(self.cfg)
            self._refresh_message_list()
            messagebox.showinfo("Importar", f"Se importaron {len(lines)} mensajes.")
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo leer el archivo:\n{exc}")

    def export_messages(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Exportar mensajes",
            defaultextension=".txt",
            filetypes=[("Archivos de texto", "*.txt")],
            parent=self.root,
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.cfg.get("messages", [])))
            messagebox.showinfo("Exportar", "Mensajes exportados correctamente.")
        except Exception as exc:
            messagebox.showerror("Error", f"No se pudo guardar el archivo:\n{exc}")

    # =========================================================================
    # CATALOG HANDLERS
    # =========================================================================
    def _selected_catalog_category(self) -> str:
        sel = self.cat_listbox.curselection()
        names = get_category_names()
        if not sel:
            return names[0]
        return names[sel[0]]

    def _on_catalog_category_selected(self, event=None) -> None:
        cat = self._selected_catalog_category()
        self.cat_msg_listbox.delete(0, tk.END)
        for msg in get_category_messages(cat):
            self.cat_msg_listbox.insert(tk.END, msg)

    def _append_unique_messages(self, new_msgs: list[str]) -> int:
        existing = set(self.cfg.get("messages", []))
        added = 0
        for m in new_msgs:
            if m not in existing:
                self.cfg["messages"].append(m)
                existing.add(m)
                added += 1
        self.cfg = save_config(self.cfg)
        self._refresh_message_list()
        return added

    def add_selected_catalog_msgs(self) -> None:
        sel = self.cat_msg_listbox.curselection()
        if not sel:
            messagebox.showinfo("Catálogo", "Selecciona al menos un mensaje de la lista.")
            return
        chosen = [self.cat_msg_listbox.get(i) for i in sel]
        added = self._append_unique_messages(chosen)
        messagebox.showinfo("Catálogo", f"Se agregaron {added} mensajes nuevos a 'Mis mensajes'.")

    def add_all_catalog_msgs(self) -> None:
        cat = self._selected_catalog_category()
        added = self._append_unique_messages(get_category_messages(cat))
        messagebox.showinfo("Catálogo", f"Se agregaron {added} mensajes nuevos de '{cat}'.")

    def replace_with_catalog(self) -> None:
        cat = self._selected_catalog_category()
        self.cfg["messages"] = get_category_messages(cat)
        self.cfg = save_config(self.cfg)
        self._refresh_message_list()
        messagebox.showinfo("Catálogo", f"'Mis mensajes' ahora usa la categoría '{cat}'.")

    def send_category_to_session(self) -> None:
        cat = self._selected_catalog_category()
        self.sess_cat_var.set(cat)
        self.sess_name_var.set(f"Sesión: {cat.split()[0]}")
        self._select_tab(2)

    # =========================================================================
    # SESSIONS HANDLERS
    # =========================================================================
    def add_session(self) -> None:
        name = self.sess_name_var.get().strip() or "Sesión"
        cat = self.sess_cat_var.get()
        start_t = self.sess_start_var.get().strip()
        end_t = self.sess_end_var.get().strip()

        for label, val in (("Hora inicio", start_t), ("Hora fin", end_t)):
            parts = val.split(":")
            if len(parts) != 2 or not all(p.isdigit() for p in parts) or not (0 <= int(parts[0]) <= 23 and 0 <= int(parts[1]) <= 59):
                messagebox.showerror("Horario inválido", f"{label} debe tener formato HH:MM (ej. 09:00).")
                return

        days = [i for i, v in enumerate(self.sess_day_vars) if v.get()]
        if not days:
            messagebox.showerror("Días", "Selecciona al menos un día de la semana.")
            return

        ms_raw = self.sess_ms_var.get().strip()
        dur_ms = None
        if ms_raw:
            try:
                dur_ms = int(ms_raw)
                if dur_ms < MIN_DURATION_MS or dur_ms > MAX_DURATION_MS:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Duración inválida",
                    f"La duración debe estar entre {MIN_DURATION_MS} y {MAX_DURATION_MS} ms (o vacía para usar la global).",
                )
                return

        new_session = {
            "id": uuid.uuid4().hex[:8],
            "name": name,
            "category": cat,
            "start_time": f"{int(start_t.split(':')[0]):02d}:{int(start_t.split(':')[1]):02d}",
            "end_time": f"{int(end_t.split(':')[0]):02d}:{int(end_t.split(':')[1]):02d}",
            "days": days,
            "duration_ms": dur_ms,
            "enabled": True,
        }
        self.cfg.setdefault("sessions", []).append(new_session)
        self.cfg = save_config(self.cfg)
        self._refresh_sessions_tree()
        self._update_status_ui()

    def toggle_selected_session(self) -> None:
        sel = self.sessions_tree.selection()
        if not sel:
            return
        sid = sel[0]
        for s in self.cfg.get("sessions", []):
            if s["id"] == sid:
                s["enabled"] = not s.get("enabled", True)
                break
        self.cfg = save_config(self.cfg)
        self._refresh_sessions_tree()
        self._update_status_ui()

    def delete_selected_session(self) -> None:
        sel = self.sessions_tree.selection()
        if not sel:
            return
        sid = sel[0]
        self.cfg["sessions"] = [s for s in self.cfg.get("sessions", []) if s["id"] != sid]
        self.cfg = save_config(self.cfg)
        self._refresh_sessions_tree()
        self._update_status_ui()

    # =========================================================================
    # SCHEDULING & FLASHING
    # =========================================================================
    def _get_effective_pool_and_cfg(self) -> tuple[list[str], dict[str, Any]]:
        active_sess = get_active_session(self.cfg)
        if active_sess:
            cat = active_sess.get("category", CUSTOM_CATEGORY_KEY)
            pool = (
                self.cfg.get("messages", [])
                if cat == CUSTOM_CATEGORY_KEY
                else get_category_messages(cat)
            )
            eff_cfg = dict(self.cfg)
            if active_sess.get("duration_ms") is not None:
                eff_cfg["duration_ms"] = active_sess["duration_ms"]
            return pool, eff_cfg

        if self.cfg.get("sessions_only", False):
            return [], self.cfg

        return self.cfg.get("messages", []), self.cfg

    def _pick_from_pool(self, pool: list[str]) -> str | None:
        if not pool:
            return None
        if self.cfg.get("order_mode") == "sequential":
            msg = pool[self._seq_index % len(pool)]
            self._seq_index = (self._seq_index + 1) % len(pool)
            return msg
        return random.choice(pool)

    def _schedule_next_flash(self) -> None:
        if self._flash_after_id is not None:
            try:
                self.root.after_cancel(self._flash_after_id)
            except Exception:
                pass
            self._flash_after_id = None

        if self._is_quitting or not self.cfg.get("enabled", True):
            return

        min_s = float(self.cfg.get("interval_min_s", 5.0))
        max_s = float(self.cfg.get("interval_max_s", 12.0))
        delay_s = random.uniform(min_s, max(min_s, max_s))
        delay_ms = max(200, int(delay_s * 1000))
        self._flash_after_id = self.root.after(delay_ms, self._run_scheduled_flash)

    def _run_scheduled_flash(self) -> None:
        self._flash_after_id = None
        if self._is_quitting or not self.cfg.get("enabled", True):
            return
        pool, eff_cfg = self._get_effective_pool_and_cfg()
        msg = self._pick_from_pool(pool)
        if msg:
            self.overlay.flash(msg, eff_cfg)
        self._schedule_next_flash()

    def test_flash(self) -> None:
        pool, eff_cfg = self._get_effective_pool_and_cfg()
        sel = self.msg_listbox.curselection()
        if sel and not get_active_session(self.cfg):
            msg = self.cfg["messages"][sel[0]]
        else:
            msg = self._pick_from_pool(pool) or self._pick_from_pool(self.cfg.get("messages", [])) or "Mensaje de prueba subliminal"
        self.overlay.flash(msg, eff_cfg)

    def toggle_enabled(self) -> None:
        self.cfg["enabled"] = not bool(self.cfg.get("enabled", True))
        self.cfg = save_config(self.cfg)
        self._update_status_ui()
        if self.cfg["enabled"]:
            self._schedule_next_flash()
        else:
            if self._flash_after_id is not None:
                try:
                    self.root.after_cancel(self._flash_after_id)
                except Exception:
                    pass
                self._flash_after_id = None
            self.overlay.hide()

    # =========================================================================
    # WINDOW / TRAY LIFECYCLE
    # =========================================================================
    def hide_to_tray(self) -> None:
        self.root.withdraw()

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.state("normal")
        self.root.lift()
        self.root.focus_force()
        self._apply_win32_taskbar_icon()

    def quit_app(self) -> None:
        if self._is_quitting:
            return
        self._is_quitting = True
        for after_id in (self._flash_after_id, self._status_after_id):
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except Exception:
                    pass
        self.overlay.destroy()
        self.tray.stop()
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def run(self) -> None:
        self.root.mainloop()
