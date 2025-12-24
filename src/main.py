# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 Adi Hezral <hezral@gmail.com>

import sys
import os
import subprocess
import threading

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
from gi.repository import Gtk, Gio, Granite, Gdk, GLib, Gst

from .window import whisWindow
from .config_manager import ConfigManager


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

    def _log_pipe(self, pipe, prefix):
        """Reads lines from a pipe and logs them."""
        with pipe:
            for line in iter(pipe.readline, ""):
                if line:
                    logging.debug(f"hyprvoice: {line.strip()}")

    def do_activate(self):
        if not self.window:
            self.window = whisWindow(application=self)
            self.window.present()

    def start_daemon(self):
        """Starts the hyprvoice daemon if not already running."""
        if self.hyprvoice_process and self.hyprvoice_process.poll() is None:
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

            self.hyprvoice_process = subprocess.Popen(
                ["hyprvoice", "serve"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                start_new_session=True
            )
            
            # Start background threads to capture and log output
            threading.Thread(target=self._log_pipe, args=(self.hyprvoice_process.stdout, "stdout"), daemon=True).start()
            threading.Thread(target=self._log_pipe, args=(self.hyprvoice_process.stderr, "stderr"), daemon=True).start()
            
        except Exception as e:
            logging.error(f"Failed to start hyprvoice: {e}")
            self.hyprvoice_process = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        Gst.init(None)

        # Apply logging level from config
        try:
            config = ConfigManager().get_config()
            if config.get("logging", {}).get("debug", False):
                logging.getLogger().setLevel(logging.DEBUG)
                logging.debug("Debug logging enabled via config.")
        except Exception as e:
            logging.error(f"Failed to apply logging level: {e}")
        
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
            self.activate()
            if self.window:
                self.window.toggle_recording()
                self.window.present()
            return 0

        if "--cancel" in args:
            logging.info("Command line: cancelling hyprvoice")
            self.activate()
            if self.window:
                self.window.cancel_recording()
                self.window.present()
            return 0
            
        self.activate()
        return 0

    def on_quit_action(self, action, param):
        logging.info("on_quit_action triggered.")
        self.quit()
        
    def do_shutdown(self):
        logging.info("Shutting down...")

        if self.window is not None:
            self.window.close()

        if self.hyprvoice_process:
            logging.info("Terminating hyprvoice daemon")
            self.hyprvoice_process.terminate()
            try:
                self.hyprvoice_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.hyprvoice_process.kill()
        
        Gtk.Application.do_shutdown(self)

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
