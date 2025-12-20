import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gdk, Gst, GLib, GObject
import cairo
import math
import random
import subprocess
import os

from .preferences import PreferencesWindow

class whisWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'whisWindow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self.props.application

        # UI State
        self.levels = [0.05] * 15
        self.last_audio_level = 0.0
        self.pipeline = None
        self.level_history = [-100.0] * 50
        self.sensitivity = 0.5
        self.scroll_speed = 40
        self.target_height = 32
        self.current_height = 32
        self.revealed = False

        # Window Settings
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_name("pill-window")
        self.set_default_size(100, 32)

        # Style context
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            #pill-window {
                background-color: rgba(0, 0, 0, 0.75);
                border-radius: 16px;
                border: 2px solid rgba(255, 255, 255, 0.1);
            }
            .overlay-btn {
                background: none;
                border: none;
                outline: none;
                box-shadow: none;
                color: rgba(255, 255, 255, 0.8);
                padding: 2px;
                margin: 0 2px;
                border-radius: 50%;
                min-width: 20px;
                min-height: 20px;
            }
            .overlay-btn:hover {
                color: white;
                background-color: rgba(255, 255, 255, 0.1);
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main Layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        # Soundwave Handle
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self.on_draw)
        self.canvas.set_size_request(-1, 32)
        self.handle = Gtk.WindowHandle()
        self.handle.set_child(self.canvas)
        self.main_box.append(self.handle)

        # Bottom Drawer (Buttons)
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revealer.set_transition_duration(300)

        self.btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_box.set_halign(Gtk.Align.CENTER)
        self.btn_box.set_valign(Gtk.Align.CENTER)
        self.btn_box.set_margin_bottom(8)

        # Buttons
        # 1. Close
        quit_btn = Gtk.Button()
        quit_btn.add_css_class("overlay-btn")
        img_quit = Gtk.Image.new_from_file(self.get_asset_path("quit.svg"))
        img_quit.set_pixel_size(16)
        quit_btn.set_child(img_quit)
        quit_btn.connect("clicked", lambda _: self.app.quit())

        # 2. Record/Stop Stack
        self.action_stack = Gtk.Stack()
        self.action_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.action_stack.set_transition_duration(200)

        self.record_btn = Gtk.Button()
        self.record_btn.add_css_class("overlay-btn")
        img_record = Gtk.Image.new_from_file(self.get_asset_path("record.svg"))
        img_record.set_pixel_size(16)
        self.record_btn.set_child(img_record)
        self.record_btn.connect("clicked", self.on_record_clicked)

        self.stop_btn = Gtk.Button()
        self.stop_btn.add_css_class("overlay-btn")
        img_stop = Gtk.Image.new_from_file(self.get_asset_path("stop.svg"))
        img_stop.set_pixel_size(16)
        self.stop_btn.set_child(img_stop)
        self.stop_btn.connect("clicked", self.on_stop_clicked)

        self.action_stack.add_named(self.record_btn, "record")
        self.action_stack.add_named(self.stop_btn, "stop")
        self.action_stack.set_visible_child_name("record")

        # 3. Preferences
        pref_btn = Gtk.Button()
        pref_btn.add_css_class("overlay-btn")
        img_pref = Gtk.Image.new_from_file(self.get_asset_path("prefs.svg"))
        img_pref.set_pixel_size(16)
        pref_btn.set_child(img_pref)
        pref_btn.connect("clicked", self.on_preferences_clicked)

        self.btn_box.append(quit_btn)
        self.btn_box.append(self.action_stack)
        self.btn_box.append(pref_btn)

        self.revealer.set_child(self.btn_box)
        self.main_box.append(self.revealer)

        # Gestures
        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self.on_window_clicked)
        self.handle.add_controller(click_gesture)

        motion_ctrl = Gtk.EventControllerMotion()
        motion_ctrl.connect("leave", self.on_hover_leave)
        self.main_box.add_controller(motion_ctrl)

        self.set_child(self.main_box)
        self.setup_audio()

        GLib.timeout_add(self.scroll_speed, self.update_animation)

    def get_asset_path(self, filename):
        # We'll use the assets folder in Project root for now
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", filename)

    def setup_audio(self):
        pipeline_str = "autoaudiosrc ! audioconvert ! level interval=50000000 ! fakesink"
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::element", self.on_level_message)
            self.pipeline.set_state(Gst.State.PLAYING)
        except Exception as e:
            print(f"Failed to setup audio: {e}")

    def on_level_message(self, bus, message):
        if message.get_structure().get_name() == "level":
            rms = message.get_structure().get_value("rms")
            avg_rms = sum(rms) / len(rms)
            self.level_history.pop(0)
            self.level_history.append(avg_rms)
            spread = max(1, max(self.level_history) - min(self.level_history))
            normalized = (avg_rms - min(self.level_history)) / spread
            normalized = max(0, min(1, normalized))
            self.last_audio_level = self.last_audio_level * 0.4 + normalized * 0.6

    def update_animation(self):
        if abs(self.target_height - self.current_height) > 0.5:
            self.current_height += (self.target_height - self.current_height) * 0.2
            self.set_default_size(100, int(self.current_height))
            self.canvas.queue_draw()

        self.levels.pop(0)
        jitter = random.uniform(0.01, 0.03)
        new_val = (self.last_audio_level * 0.9) + jitter
        self.levels.append(new_val)
        self.canvas.queue_draw()
        return True

    def on_draw(self, drawing_area, cr, width, height):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        thickness, gap, margin = 2, 2, 5
        usable_width = width - 2 * margin
        usable_height = height - 2 * margin
        num_bars = int((usable_width + gap) // (thickness + gap))
        
        if len(self.levels) != num_bars:
            if len(self.levels) < num_bars:
                self.levels = [0.05] * (num_bars - len(self.levels)) + self.levels
            else:
                self.levels = self.levels[-num_bars:]

        total_bars_width = (num_bars * thickness) + ((num_bars - 1) * gap)
        start_x = margin + (usable_width - total_bars_width) / 2
        mid_y = height / 2

        for i, level in enumerate(self.levels):
            x = start_x + (i * (thickness + gap)) + (thickness / 2)
            bar_height = (level * self.sensitivity * (usable_height - 2)) + 2
            cr.set_source_rgba(1, 1, 1, 0.5)
            cr.set_line_width(thickness)
            cr.set_line_cap(1)
            cr.move_to(x, mid_y - bar_height / 2)
            cr.line_to(x, mid_y + bar_height / 2)
            cr.stroke()

    def on_window_clicked(self, gesture, n_press, x, y):
        self.revealed = True
        self.target_height = 64
        self.revealer.set_reveal_child(True)

    def on_hover_leave(self, ctrl):
        if self.revealed:
            self.revealed = False
            self.target_height = 32
            self.revealer.set_reveal_child(False)

    def on_record_clicked(self, btn):
        subprocess.Popen(["hyprvoice", "toggle"])
        self.action_stack.set_visible_child_name("stop")

    def on_stop_clicked(self, btn):
        subprocess.Popen(["hyprvoice", "toggle"])
        self.action_stack.set_visible_child_name("record")

    def on_preferences_clicked(self, btn):
        win = PreferencesWindow(self)
        win.present()

        
