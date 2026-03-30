#!/usr/bin/env python3

import random
import string
import sys
from pathlib import Path

import gi
import pyperclip

gi.require_version('Gtk', '4.0')

# tomllib is built in Python 3.11+; fallback to tomli
if sys.version_info >= (3, 11):
    import tomllib as toml
else:
    import tomli as toml

from gi.repository import Gdk, Gio, GLib, Gtk

# keep references to transient error windows so they are not garbage-collected
_open_error_windows = []


def generate_random_text():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=10))

def show_error_dialog(parent, title, message, app=None):
    # Create an app-owned window if app is provided so the application
    # does not quit while the error window is visible.
    if app is not None:
        win = Gtk.ApplicationWindow(application=app, title=title)
    else:
        win = Gtk.Window(title=title)

    win.set_modal(True)
    if parent is not None:
        try:
            win.set_transient_for(parent)
        except Exception:
            pass

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=12, margin_bottom=12, margin_start=12, margin_end=12)
    label = Gtk.Label(label=message)
    label.set_wrap(True)
    label.set_justify(Gtk.Justification.LEFT)
    box.append(label)

    close_btn = Gtk.Button(label="Fermer")
    close_btn.connect("clicked", lambda w: win.destroy())
    box.append(close_btn)

    win.set_child(box)
    _open_error_windows.append(win)
    win.connect("destroy", lambda w: _open_error_windows.remove(w) if w in _open_error_windows else None)
    win.present()
    return None


def load_texts_from_toml():
    # Always look for texts.toml in the same directory as this script
    p = Path(__file__).parent / 'texts.toml'
    if not p.exists():
        raise FileNotFoundError(f"Fichier {p} introuvable")
    data = toml.loads(p.read_text(encoding='utf-8'))
    clips = data.get('clips')
    if not isinstance(clips, list) or not clips:
        raise ValueError("'clips' doit être une liste non-vide dans texts.toml")
    return clips


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app, texts):
        super().__init__(application=app, title="Poker Clipboard Shortcuts")
        self.set_default_size(156, 175)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.set_child(box)

        for text in texts:
            display_label = text.splitlines()[0] if text else ""
            button = Gtk.Button(label=display_label)
            button.connect("clicked", self.on_button_clicked, text)
            box.append(button)

        # Set large font
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data("""
        button {
            font-size: 15px;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

    def on_button_clicked(self, widget, text):
        pyperclip.copy(text)

class PokerApp(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        try:
            texts = load_texts_from_toml()
        except Exception as exc:
            # no main window if loading fails
            show_error_dialog(None, "Erreur de chargement", f"Impossible de charger texts.toml: {exc}", app=app)
            return

        win = AppWindow(app, texts)
        self.window = win
        win.present()


if __name__ == "__main__":
    app = PokerApp()
    app.run()