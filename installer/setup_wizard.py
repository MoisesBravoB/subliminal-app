import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk
import winreg

APP_NAME = "Subliminal Flash"
APP_VERSION = "1.2.0"
APP_PUBLISHER = "Subliminal Flash"
EXE_NAME = "SubliminalFlash.exe"
ICON_NAME = "subliminal.ico"
REG_UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\SubliminalFlash"
REG_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_RUN_NAME = "SubliminalFlashApp"

# Nintendo NES Minimalist Gray + Apple Palette
BG_MAIN = "#E4E3DF"
BG_HEADER = "#262628"
BG_CARD = "#F4F3EF"
BG_INPUT = "#FFFFFF"
BG_TRACK = "#D5D3CC"
BORDER = "#C8C6BE"
TEXT_PRIMARY = "#1D1D1F"
TEXT_MUTED = "#6E6E73"
TEXT_ON_DARK = "#F5F5F7"
TEXT_MUTED_DARK = "#A1A1A6"
NES_RED = "#D62828"
NES_RED_HOVER = "#B51E1E"
BTN_LIGHT = "#DFDDD7"
BTN_LIGHT_HOVER = "#CECCC5"
SUCCESS = "#15803D"

CREATE_NO_WINDOW = 0x08000000


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


def _resource_path(rel: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / rel


def _default_install_dir() -> Path:
    local_app = os.environ.get("LOCALAPPDATA", str(Path.home()))
    return Path(local_app) / "Programs" / "SubliminalFlash"


def _run_ps(script: str) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        creationflags=CREATE_NO_WINDOW,
        check=False,
    )


def _create_shortcut(lnk_path: Path, target: Path, icon: Path, description: str, args: str = "") -> None:
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    ps = (
        f"$ws = New-Object -ComObject WScript.Shell; "
        f"$sc = $ws.CreateShortcut('{str(lnk_path).replace(chr(39), chr(39)*2)}'); "
        f"$sc.TargetPath = '{str(target).replace(chr(39), chr(39)*2)}'; "
        f"$sc.WorkingDirectory = '{str(target.parent).replace(chr(39), chr(39)*2)}'; "
        f"$sc.IconLocation = '{str(icon).replace(chr(39), chr(39)*2)},0'; "
        f"$sc.Description = '{description.replace(chr(39), chr(39)*2)}'; "
    )
    if args:
        ps += f"$sc.Arguments = '{args.replace(chr(39), chr(39)*2)}'; "
    ps += "$sc.Save()"
    _run_ps(ps)


def _get_special_folder(name: str) -> Path:
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"[Environment]::GetFolderPath('{name}')"],
        capture_output=True,
        text=True,
        creationflags=CREATE_NO_WINDOW,
    )
    out = res.stdout.strip()
    if out:
        return Path(out)
    return Path.home() / ("Desktop" if name == "Desktop" else "AppData/Roaming/Microsoft/Windows/Start Menu/Programs")


def _write_uninstaller(install_dir: Path, desktop_lnk: Path, startmenu_dir: Path) -> Path:
    ps1_path = install_dir / "uninstall.ps1"
    vbs_path = install_dir / "Desinstalar.vbs"

    ps1_content = f"""$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Windows.Forms
$ans = [System.Windows.Forms.MessageBox]::Show(
    '¿Deseas desinstalar Subliminal Flash de tu computadora?',
    'Desinstalar Subliminal Flash',
    [System.Windows.Forms.MessageBoxButtons]::YesNo,
    [System.Windows.Forms.MessageBoxIcon]::Question
)
if ($ans -ne [System.Windows.Forms.DialogResult]::Yes) {{ exit 0 }}

Stop-Process -Name 'SubliminalFlash' -Force
Start-Sleep -Milliseconds 400

Remove-Item -LiteralPath '{desktop_lnk}' -Force
Remove-Item -LiteralPath '{startmenu_dir}' -Recurse -Force
Remove-Item -Path 'HKCU:\\{REG_UNINSTALL_KEY}' -Force
Remove-ItemProperty -Path 'HKCU:\\{REG_RUN_KEY}' -Name '{REG_RUN_NAME}'

[System.Windows.Forms.MessageBox]::Show(
    'Subliminal Flash se ha desinstalado correctamente.',
    'Desinstalación completa',
    [System.Windows.Forms.MessageBoxButtons]::OK,
    [System.Windows.Forms.MessageBoxIcon]::Information
)

$dir = '{install_dir}'
Start-Process cmd.exe -ArgumentList "/c timeout /t 2 /nobreak >nul & rmdir /s /q `"$dir`"" -WindowStyle Hidden
"""
    ps1_path.write_text(ps1_content, encoding="utf-8")

    vbs_content = (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        'Set fso = CreateObject("Scripting.FileSystemObject")\n'
        'dir = fso.GetParentFolderName(WScript.ScriptFullName)\n'
        'WshShell.Run "powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & dir & "\\uninstall.ps1""", 0, False\n'
    )
    vbs_path.write_text(vbs_content, encoding="utf-8")
    return vbs_path


def _register_uninstall_entry(install_dir: Path, exe_path: Path, icon_path: Path, uninstaller_vbs: Path) -> None:
    size_kb = max(1, int(exe_path.stat().st_size / 1024))
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_UNINSTALL_KEY) as key:
        winreg.SetValueEx(key, "DisplayName", 0, winreg.REG_SZ, APP_NAME)
        winreg.SetValueEx(key, "DisplayVersion", 0, winreg.REG_SZ, APP_VERSION)
        winreg.SetValueEx(key, "Publisher", 0, winreg.REG_SZ, APP_PUBLISHER)
        winreg.SetValueEx(key, "InstallLocation", 0, winreg.REG_SZ, str(install_dir))
        winreg.SetValueEx(key, "DisplayIcon", 0, winreg.REG_SZ, str(icon_path))
        winreg.SetValueEx(key, "UninstallString", 0, winreg.REG_SZ, f'wscript.exe "{uninstaller_vbs}"')
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def _set_autostart(exe_path: Path, enable: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enable:
            winreg.SetValueEx(key, REG_RUN_NAME, 0, winreg.REG_SZ, f'"{exe_path}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, REG_RUN_NAME)
            except FileNotFoundError:
                pass


class SetupWizard:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(f"Instalador — {APP_NAME}")
        self.root.configure(bg=BG_MAIN)
        self.root.resizable(False, False)
        self.font_ui = _pick_apple_font(self.root)

        ico = _resource_path(f"assets/{ICON_NAME}")
        if ico.exists():
            try:
                self.root.iconbitmap(str(ico))
            except Exception:
                pass

        self.install_dir_var = tk.StringVar(value=str(_default_install_dir()))
        self.desktop_var = tk.BooleanVar(value=True)
        self.startmenu_var = tk.BooleanVar(value=True)
        self.autostart_var = tk.BooleanVar(value=False)
        self.launch_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar(value="Listo para instalar.")

        self._installing = False
        self._installed_exe: Path | None = None

        self._setup_styles()
        self._build_ui()
        self._center_window()

    def _f(self, size: int, weight: str = "normal") -> tuple:
        return (self.font_ui, size, weight)

    def _center_window(self) -> None:
        self.root.update_idletasks()
        w = max(580, self.root.winfo_reqwidth() + 16)
        h = max(510, self.root.winfo_reqheight() + 14)
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw - w)//2}+{(sh - h)//2}")

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(
            "NES.Horizontal.TProgressbar",
            troughcolor=BG_TRACK,
            background=NES_RED,
            bordercolor=BORDER,
            lightcolor=NES_RED,
            darkcolor=NES_RED,
        )

    def _build_ui(self) -> None:
        # Bottom actions (always visible at any DPI)
        footer = tk.Frame(self.root, bg=BG_MAIN)
        footer.pack(side="bottom", fill="x", padx=18, pady=(4, 16))

        self.btn_cancel = self._make_btn(footer, "Cancelar", self.root.destroy, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY)
        self.btn_cancel.pack(side="left")

        self.btn_install = self._make_btn(footer, "Instalar ahora", self._start_install, bg=NES_RED, hover=NES_RED_HOVER, fg=TEXT_ON_DARK)
        self.btn_install.pack(side="right")

        # NES Charcoal Console Banner + Red Stripe
        banner_wrap = tk.Frame(self.root, bg=BG_HEADER)
        banner_wrap.pack(fill="x")

        banner = tk.Frame(banner_wrap, bg=BG_HEADER, padx=22, pady=16)
        banner.pack(fill="x")

        tk.Label(
            banner,
            text=f"Instalar {APP_NAME}",
            font=self._f(16, "bold"),
            fg=TEXT_ON_DARK,
            bg=BG_HEADER,
        ).pack(anchor="w")

        tk.Label(
            banner,
            text=f"VERSIÓN {APP_VERSION}  •  MENSAJES SUBLIMINALES PARA WINDOWS",
            font=self._f(7, "bold"),
            fg=TEXT_MUTED_DARK,
            bg=BG_HEADER,
        ).pack(anchor="w", pady=(3, 0))

        tk.Frame(banner_wrap, bg=NES_RED, height=3).pack(fill="x")

        # Body card
        card = tk.Frame(self.root, bg=BG_CARD, padx=20, pady=16, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=18, pady=(14, 10))

        hdr1 = tk.Frame(card, bg=BG_CARD)
        hdr1.pack(fill="x", pady=(0, 6))
        tk.Frame(hdr1, bg=NES_RED, width=3, height=12).pack(side="left", padx=(0, 7))
        tk.Label(hdr1, text="CARPETA DE INSTALACIÓN", font=self._f(8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        path_row = tk.Frame(card, bg=BG_CARD)
        path_row.pack(fill="x", pady=(0, 14))

        self.dir_entry = tk.Entry(
            path_row,
            textvariable=self.install_dir_var,
            bg=BG_INPUT,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="flat",
            font=self._f(9),
            highlightthickness=1,
            highlightbackground=BORDER,
        )
        self.dir_entry.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        self.btn_browse = self._make_btn(path_row, "Cambiar...", self._browse_dir, bg=BTN_LIGHT, hover=BTN_LIGHT_HOVER, fg=TEXT_PRIMARY)
        self.btn_browse.pack(side="right")

        hdr2 = tk.Frame(card, bg=BG_CARD)
        hdr2.pack(fill="x", pady=(0, 6))
        tk.Frame(hdr2, bg=NES_RED, width=3, height=12).pack(side="left", padx=(0, 7))
        tk.Label(hdr2, text="OPCIONES", font=self._f(8, "bold"), fg=TEXT_MUTED, bg=BG_CARD).pack(side="left")

        for text, var in (
            ("Crear acceso directo en el Escritorio", self.desktop_var),
            ("Crear acceso directo en el Menú Inicio", self.startmenu_var),
            ("Iniciar automáticamente al encender Windows", self.autostart_var),
            ("Abrir Subliminal Flash al terminar la instalación", self.launch_var),
        ):
            tk.Checkbutton(
                card,
                text=text,
                variable=var,
                bg=BG_CARD,
                fg=TEXT_PRIMARY,
                selectcolor=BG_INPUT,
                activebackground=BG_CARD,
                activeforeground=TEXT_PRIMARY,
                font=self._f(9),
            ).pack(anchor="w", pady=2)

        # Progress
        self.progress = ttk.Progressbar(
            card,
            mode="determinate",
            maximum=100,
            style="NES.Horizontal.TProgressbar",
        )
        self.progress.pack(fill="x", pady=(16, 6))

        self.status_label = tk.Label(
            card,
            textvariable=self.status_var,
            font=self._f(9),
            fg=TEXT_MUTED,
            bg=BG_CARD,
        )
        self.status_label.pack(anchor="w")

    def _make_btn(self, parent, text: str, cmd, bg: str, hover: str, fg: str) -> tk.Button:
        btn = tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg=fg,
            activebackground=hover,
            activeforeground=fg,
            relief="flat",
            borderwidth=0,
            font=self._f(9, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
        )
        btn.bind("<Enter>", lambda e: btn.configure(bg=hover) if btn["state"] == "normal" else None)
        btn.bind("<Leave>", lambda e: btn.configure(bg=bg) if btn["state"] == "normal" else None)
        return btn

    def _browse_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="Seleccionar carpeta de instalación",
            initialdir=self.install_dir_var.get(),
            parent=self.root,
        )
        if chosen:
            p = Path(chosen)
            if p.name.lower() != "subliminalflash":
                p = p / "SubliminalFlash"
            self.install_dir_var.set(str(p))

    def _set_progress(self, value: int, text: str) -> None:
        self.root.after(0, lambda: (self.progress.configure(value=value), self.status_var.set(text)))

    def _start_install(self) -> None:
        if self._installing:
            return
        self._installing = True
        self.btn_install.configure(state="disabled", text="Instalando...")
        self.btn_browse.configure(state="disabled")
        self.dir_entry.configure(state="disabled")
        threading.Thread(target=self._do_install, daemon=True).start()

    def _do_install(self) -> None:
        try:
            install_dir = Path(self.install_dir_var.get().strip())
            src_exe = _resource_path(f"payload/{EXE_NAME}")
            src_ico = _resource_path(f"assets/{ICON_NAME}")

            if not src_exe.exists():
                raise FileNotFoundError(f"No se encontró el archivo de la aplicación: {src_exe}")

            self._set_progress(15, "Cerrando instancias anteriores...")
            subprocess.run(
                ["taskkill", "/IM", EXE_NAME, "/F"],
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )

            self._set_progress(35, "Copiando archivos...")
            install_dir.mkdir(parents=True, exist_ok=True)
            dst_exe = install_dir / EXE_NAME
            dst_ico = install_dir / ICON_NAME
            shutil.copy2(src_exe, dst_exe)
            if src_ico.exists():
                shutil.copy2(src_ico, dst_ico)

            desktop_dir = _get_special_folder("Desktop")
            desktop_lnk = desktop_dir / f"{APP_NAME}.lnk"
            programs_dir = _get_special_folder("Programs")
            startmenu_dir = programs_dir / APP_NAME

            self._set_progress(60, "Creando accesos directos...")
            if self.desktop_var.get():
                _create_shortcut(desktop_lnk, dst_exe, dst_ico, f"{APP_NAME} - Mensajes subliminales")

            uninstaller_vbs = _write_uninstaller(install_dir, desktop_lnk, startmenu_dir)

            if self.startmenu_var.get():
                _create_shortcut(startmenu_dir / f"{APP_NAME}.lnk", dst_exe, dst_ico, f"{APP_NAME}")
                _create_shortcut(
                    startmenu_dir / f"Desinstalar {APP_NAME}.lnk",
                    Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "wscript.exe",
                    dst_ico,
                    f"Desinstalar {APP_NAME}",
                    args=f'"{uninstaller_vbs}"',
                )

            self._set_progress(82, "Registrando en Windows...")
            _register_uninstall_entry(install_dir, dst_exe, dst_ico, uninstaller_vbs)
            _set_autostart(dst_exe, bool(self.autostart_var.get()))

            self._installed_exe = dst_exe
            self._set_progress(100, "¡Instalación completada con éxito!")
            self.root.after(0, self._on_install_done)
        except Exception as exc:
            self.root.after(0, lambda: self._on_install_error(str(exc)))

    def _on_install_done(self) -> None:
        self.status_label.configure(fg=SUCCESS)
        self.btn_cancel.configure(text="Cerrar")
        self.btn_install.configure(state="normal", text="Finalizar", command=self._finish)

    def _on_install_error(self, err: str) -> None:
        self._installing = False
        self.btn_install.configure(state="normal", text="Reintentar")
        self.btn_browse.configure(state="normal")
        self.dir_entry.configure(state="normal")
        self.status_var.set("Ocurrió un error durante la instalación.")
        messagebox.showerror("Error de instalación", f"No se pudo completar la instalación:\n\n{err}", parent=self.root)

    def _finish(self) -> None:
        if self.launch_var.get() and self._installed_exe and self._installed_exe.exists():
            try:
                os.startfile(str(self._installed_exe))
            except Exception:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SubliminalFlash.Installer.1.2")
    except Exception:
        pass
    SetupWizard().run()


if __name__ == "__main__":
    main()
