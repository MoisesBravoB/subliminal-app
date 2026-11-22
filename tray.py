import threading
from typing import Callable

from PIL import Image, ImageDraw
import pystray


def _create_icon_image(active: bool) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if active:
        shell = (228, 227, 223, 255)   # NES warm gray
        bezel = (43, 43, 45, 255)      # NES charcoal
        led = (214, 40, 40, 255)       # NES classic red
    else:
        shell = (180, 179, 175, 255)
        bezel = (95, 95, 100, 255)
        led = (140, 140, 145, 255)

    draw.rounded_rectangle((4, 4, size - 4, size - 4), radius=14, fill=shell, outline=bezel, width=4)
    draw.rectangle((6, 22, size - 6, 42), fill=bezel)
    draw.ellipse((23, 23, 41, 41), fill=led)
    return img


class TrayManager:
    """System tray controller running in a background thread."""

    def __init__(
        self,
        on_open: Callable[[], None],
        on_toggle: Callable[[], None],
        on_test: Callable[[], None],
        on_quit: Callable[[], None],
        get_enabled: Callable[[], bool],
    ):
        self._on_open = on_open
        self._on_toggle = on_toggle
        self._on_test = on_test
        self._on_quit = on_quit
        self._get_enabled = get_enabled
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._icon is not None:
            return
        active = self._get_enabled()
        menu = pystray.Menu(
            pystray.MenuItem("Abrir configuración", self._handle_open, default=True),
            pystray.MenuItem(
                lambda item: "Pausar destellos" if self._get_enabled() else "Activar destellos",
                self._handle_toggle,
            ),
            pystray.MenuItem("Probar destello ahora", self._handle_test),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._handle_quit),
        )
        self._icon = pystray.Icon(
            "SubliminalFlash",
            _create_icon_image(active),
            self._tooltip_text(active),
            menu,
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def update_state(self, active: bool) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = _create_icon_image(active)
            self._icon.title = self._tooltip_text(active)
            self._icon.update_menu()
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None

    def _tooltip_text(self, active: bool) -> str:
        estado = "Activo" if active else "Pausado"
        return f"Subliminal Flash ({estado})"

    def _handle_open(self, icon, item) -> None:
        self._on_open()

    def _handle_toggle(self, icon, item) -> None:
        self._on_toggle()

    def _handle_test(self, icon, item) -> None:
        self._on_test()

    def _handle_quit(self, icon, item) -> None:
        self._on_quit()
