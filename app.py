import ctypes
import os
import sys

from ui import SubliminalApp

MUTEX_NAME = "Global\\SubliminalFlashApp_SingleInstance_Mutex"


def _enable_dpi_awareness() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _acquire_single_instance_mutex():
    if os.name != "nt":
        return None
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    last_error = kernel32.GetLastError()
    # ERROR_ALREADY_EXISTS = 183
    if last_error == 183:
        return False
    return mutex


def _set_app_user_model_id() -> None:
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SubliminalFlash.App.1.2")
    except Exception:
        pass


def main() -> None:
    _enable_dpi_awareness()
    _set_app_user_model_id()

    mutex = _acquire_single_instance_mutex()
    if mutex is False:
        # Already running in background
        try:
            ctypes.windll.user32.MessageBoxW(
                0,
                "Subliminal Flash ya se está ejecutando en segundo plano.\n\nRevisa el ícono en la bandeja del sistema (esquina inferior derecha).",
                "Subliminal Flash",
                0x40,
            )
        except Exception:
            pass
        sys.exit(0)

    start_minimized = "--minimized" in sys.argv
    app = SubliminalApp(start_minimized_arg=start_minimized)
    app.run()


if __name__ == "__main__":
    main()
