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
        except (TypeError, AttributeError):
            # parent may not be a suitable Gdk window or method may be absent
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


def load_snippets_from_toml():
    # Always look for snippets.toml in the same directory as this script
    p = Path(__file__).parent / 'snippets.toml'
    if not p.exists():
        raise FileNotFoundError(f"Fichier {p} introuvable")
    data = toml.loads(p.read_text(encoding='utf-8'))
    clips = data.get('clips')
    if not isinstance(clips, list) or not clips:
        raise ValueError("'clips' doit être une liste non-vide dans snippets.toml")
    return clips


class AppWindow(Gtk.ApplicationWindow):
    def __init__(self, app, snippets):
        super().__init__(application=app, title="Quick Snippets")
        self.set_default_size(156, 175)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        # Allow the box to expand with the window when resized
        box.set_hexpand(True)
        box.set_vexpand(True)
        # Make children share space equally so buttons stretch
        box.set_homogeneous(True)
        self.set_child(box)

        for text in snippets:
            display_label = text.splitlines()[0] if text else ""
            button = Gtk.Button(label=display_label)
            # Let each button expand to fill available vertical space
            button.set_vexpand(True)
            button.set_hexpand(True)
            button.set_valign(Gtk.Align.FILL)
            button.connect("clicked", self.on_button_clicked, text)
            # Right-click gesture: reset background without copying
            try:
                rc = Gtk.GestureClick()
                rc.set_button(3)
                rc.connect("pressed", self.on_button_right_clicked)
                # attach gesture/controller to the button
                button.add_controller(rc)
            except (AttributeError, TypeError):
                # If gestures/controllers aren't available, ignore gracefully
                pass
            box.append(button)

        # Set large font
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data("""
        button {
            font-size: 10px;
            padding: 0px 0px;
            min-height: 0;
            height: 1.0em;
            margin: 0;
        }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_USER
        )

    def on_button_clicked(self, widget, text):
        pyperclip.copy(text)
        # Add a style class so the global CSS applies and the background stays colored
        widget.get_style_context().add_class('copied')
        # try to reinforce styling by adding a small inline provider too
        css = Gtk.CssProvider()
        css.load_from_data(f"button.copied {{ background-color: #dddef6; background-image: none; color: #000000 }}")
        widget.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_USER)
        # keep provider reference so we can remove it on right-click
        widget.set_data('copied_css', css)

    def on_button_right_clicked(self, gesture, n_press, x, y):
        # This handler will be attached to the button via a Gtk.GestureClick.
        # It should reset the button's style without copying its text.
        widget = gesture.get_widget()
        ctx = widget.get_style_context()
        ctx.remove_class('copied')
        provider = widget.get_data('copied_css') if hasattr(widget, 'get_data') else None
        if provider:
            try:
                ctx.remove_provider(provider)
            except (AttributeError, TypeError):
                pass
            widget.set_data('copied_css', None)


class MainWindow(Gtk.Application):
    def __init__(self):
        super().__init__()
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        # Build a tuple of decode exceptions provided by the toml backend
        _toml_decode_exc = getattr(toml, 'TOMLDecodeError', None) or getattr(toml, 'TomlDecodeError', None)
        _expected_errors = (FileNotFoundError, ValueError) + ((_toml_decode_exc,) if _toml_decode_exc is not None else ())
        try:
            snippets = load_snippets_from_toml()
        except _expected_errors as exc:
            # no main window if loading fails; report known errors
            show_error_dialog(None, f"Can't read snippets.toml: {exc}", app=app)
            return

        win = AppWindow(app, snippets)
        self.window = win
        win.present()


if __name__ == "__main__":
    app = MainWindow()
    app.run()