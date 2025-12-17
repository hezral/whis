# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 Adi Hezral <hezral@gmail.com>

import sys
import os
import subprocess

import gi
import logging
import sys

# Configure logging
log_dir = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "whis.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%Y/%m/%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
gi.require_version('Gtk', '4.0')
gi.require_version('Granite', '7.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gio, Granite, Gdk, GLib

from .window import whisWindow


class Application(Gtk.Application):

    app_id = "com.github.hezral.whis"
    gio_settings = Gio.Settings(schema_id=app_id)
    gtk_settings = Gtk.Settings().get_default()
    granite_settings = Granite.Settings.get_default()

    def __init__(self):
        super().__init__(application_id=self.app_id,
                         flags=Gio.ApplicationFlags.FLAGS_NONE | Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.hyprvoice_process = None
        self.window = None

    def do_activate(self):
        if not self.window:
            self.window = whisWindow(application=self)
        self.window.present()

    def start_daemon(self):
        """Starts the hyprvoice daemon if not already running."""
        if self.hyprvoice_process and self.hyprvoice_process.poll() is None:
            logging.info("Daemon is already running.")
            return

        try:
            # Clean up stale PID file
            pid_path = os.path.expanduser("~/.cache/hyprvoice/hyprvoice.pid")
            xdg_cache = os.environ.get('XDG_CACHE_HOME')
            
            if xdg_cache:
                 pid_path_xdg = os.path.join(xdg_cache, "hyprvoice", "hyprvoice.pid")
                 if os.path.exists(pid_path_xdg):
                      pid_path = pid_path_xdg

            if os.path.exists(pid_path):
                logging.info(f"Removing stale PID file: {pid_path}")
                os.remove(pid_path)

            self.hyprvoice_process = subprocess.Popen(["hyprvoice", "serve"])
            
        except Exception as e:
            logging.error(f"Failed to start hyprvoice: {e}")
            self.hyprvoice_process = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        
        # Keep application alive even when window is closed
        self.hold()

        # Start hyprvoice service
        self.start_daemon()
        
        # Support quiting app using Super+Q
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", self.on_quit_action)
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>Q", "Escape"])

        prefers_color_scheme = self.granite_settings.get_prefers_color_scheme()
        self.gtk_settings.set_property("gtk-application-prefer-dark-theme", prefers_color_scheme)
        self.granite_settings.connect("notify::prefers-color-scheme", self.on_prefers_color_scheme)

        if "io.elementary.stylesheet" not in self.gtk_settings.props.gtk_theme_name:
            self.gtk_settings.set_property("gtk-theme-name", "io.elementary.stylesheet.blueberry")

        # set CSS provider
        provider = Gtk.CssProvider()
        provider.load_from_path(os.path.join(os.path.dirname(__file__), "data", "application.css"))
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        # prepend custom path for icon theme
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        icon_theme.add_search_path(os.path.join(os.path.dirname(__file__), "data", "icons"))

    
    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        
        if "--toggle" in args:
            logging.info("Command line: toggling hyprvoice")
            try:
                subprocess.Popen(["hyprvoice", "toggle"])
                # Hide window if visible to avoid stealing focus
                if self.window and self.window.is_visible():
                    self.window.hide()
            except Exception as e:
                logging.error(f"Failed to toggle hyprvoice: {e}")
            return 0
            
        self.activate()
        return 0

    def on_quit_action(self, action, param):
        if self.hyprvoice_process:
            self.hyprvoice_process.terminate()
        self.quit()

    def on_prefers_color_scheme(self, *args):
        prefers_color_scheme = self.granite_settings.get_prefers_color_scheme()
        self.gtk_settings.set_property("gtk-application-prefer-dark-theme", prefers_color_scheme)

def main(version):
    app = Application()
    version = os.environ.get('VERSION')
    if version is None:
        version = '0.1.0'
    logging.info(version)
    return app.run(sys.argv)
