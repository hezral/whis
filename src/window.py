# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 Adi Hezral <hezral@gmail.com>

import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject
import subprocess

from .mode_switch import ModeSwitch
from .preferences import PreferencesWindow

class whisWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'whisWindow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.app = self.props.application

        light = Gtk.Image.new_from_icon_name("display-brightness-symbolic")
        dark = Gtk.Image.new_from_icon_name("weather-clear-night-symbolic")
        modeswitch = ModeSwitch(light, dark, None, None)
        modeswitch.switch.bind_property("active", self.app.gtk_settings, "gtk-application-prefer-dark-theme", GObject.BindingFlags.SYNC_CREATE)

        header = Gtk.HeaderBar()
        header.props.show_title_buttons = True
        # header.props.decoration_layout = "close:" # Gtk4 HeaderBar uses system layout by default or window settings
        
        # Preferences Button
        pref_btn = Gtk.Button.new_from_icon_name("emblem-system-symbolic")
        pref_btn.connect("clicked", self.on_preferences_clicked)
        header.pack_end(pref_btn)
        
        header.pack_end(modeswitch)
        self.set_titlebar(header)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        vbox.set_margin_top(20)
        vbox.set_margin_bottom(20)
        vbox.set_margin_start(20)
        vbox.set_margin_end(20)

        # Buttons Grid
        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_halign(Gtk.Align.CENTER)
        vbox.append(grid)

        # Start (Serve)
        btn_serve = Gtk.Button(label="Start Daemon")
        btn_serve.connect("clicked", self.on_serve_clicked)
        grid.attach(btn_serve, 0, 0, 1, 1)

        # Stop
        btn_stop = Gtk.Button(label="Stop Daemon")
        btn_stop.connect("clicked", self.on_stop_clicked)
        grid.attach(btn_stop, 1, 0, 1, 1)

        # Toggle
        btn_toggle = Gtk.Button(label="Toggle Recording")
        btn_toggle.connect("clicked", self.on_toggle_clicked)
        grid.attach(btn_toggle, 0, 1, 1, 1)

        # Cancel
        btn_cancel = Gtk.Button(label="Cancel Operation")
        btn_cancel.connect("clicked", self.on_cancel_clicked)
        grid.attach(btn_cancel, 1, 1, 1, 1)

        # Status
        btn_status = Gtk.Button(label="Check Status")
        btn_status.connect("clicked", self.on_status_clicked)
        grid.attach(btn_status, 0, 2, 1, 1)

        # Version
        btn_version = Gtk.Button(label="Version")
        btn_version.connect("clicked", self.on_version_clicked)
        grid.attach(btn_version, 1, 2, 1, 1)

        # Output Area
        output_label = Gtk.Label(label="Command Output", xalign=0)
        output_label.add_css_class("heading")
        vbox.append(output_label)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.output_view = Gtk.TextView()
        self.output_view.set_editable(False)
        self.output_view.set_monospace(True)
        self.output_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.output_buffer = self.output_view.get_buffer()
        
        scrolled.set_child(self.output_view)
        # Add a frame around it for better visuals
        frame = Gtk.Frame()
        frame.set_child(scrolled)
        vbox.append(frame)

        window_handle = Gtk.WindowHandle()
        window_handle.set_child(vbox)
        self.set_child(window_handle)

        self.set_default_size(600, 500)

    def append_output(self, text):
        end_iter = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end_iter, text + "\n")
        # Scroll to bottom
        mark = self.output_buffer.create_mark(None, end_iter, False)
        self.output_view.scroll_to_mark(mark, 0.0, True, 0.0, 1.0)
    
    def run_command(self, command):
        self.append_output(f"> {' '.join(command)}")
        try:
            result = subprocess.run(command, capture_output=True, text=True)
            if result.stdout:
                self.append_output(result.stdout.strip())
            if result.stderr:
                self.append_output(f"Error: {result.stderr.strip()}")
        except Exception as e:
            self.append_output(f"Execution failed: {e}")

    def on_serve_clicked(self, btn):
        self.append_output("> Starting hyprvoice serve...")
        try:
            # Use the centralized start method in Application to ensure single instance & log monitoring
            self.app.start_daemon()
            self.append_output("Daemon started (monitored).")
        except Exception as e:
            self.append_output(f"Failed to start daemon: {e}")

    def on_stop_clicked(self, btn):
        self.run_command(["hyprvoice", "stop"])

    def on_toggle_clicked(self, btn):
        self.run_command(["hyprvoice", "toggle"])

    def on_cancel_clicked(self, btn):
        self.run_command(["hyprvoice", "cancel"])

    def on_status_clicked(self, btn):
        self.run_command(["hyprvoice", "status"])

    def on_version_clicked(self, btn):
        self.run_command(["hyprvoice", "version"])
        # self.show_all() is not needed in Gtk4

    def on_preferences_clicked(self, btn):
        win = PreferencesWindow(self)
        win.present()

        
