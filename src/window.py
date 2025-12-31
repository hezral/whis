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
import logging

from .preferences import PreferencesWindow
from .logging_utils import log_function_calls

# Initialize module-level logger
logger = logging.getLogger(__name__)

class whisWindow(Gtk.ApplicationWindow):
    __gtype_name__ = 'whisWindow'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = self.props.application

        # UI State
        self.num_bars = 20 # Reverted to 20 as requested
        self.levels = [0.05] * self.num_bars
        self.bar_weights = [random.uniform(0.3, 1.0) for _ in range(self.num_bars)]
        self.last_audio_level = 0.0
        self.pipeline = None
        self.level_history = [-100.0] * 50
        self.sensitivity = 0.5
        self.scroll_speed = 40
        self.target_height = 24
        self.current_height = 24
        self.revealed = False
        self.recording = False

        # Window Settings
        self.set_title("Whis")
        self.set_icon_name(self.app.app_id)
        self.set_decorated(False)
        self.set_name("pill-window")
        self.set_default_size(100, 24)
        self.set_size_request(100, 24)
        self.set_resizable(True)
        self.set_valign(Gtk.Align.START)

        # Main Layout
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_size_request(96, -1)
        self.main_box.set_hexpand(False)
        self.main_box.set_halign(Gtk.Align.CENTER)
        
        # Soundwave Handle
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self.on_draw)
        self.canvas.set_size_request(96, 20)
        self.handle = Gtk.WindowHandle()
        self.handle.set_child(self.canvas)
        self.handle.set_vexpand(False)
        self.handle.set_valign(Gtk.Align.START)
        self.main_box.append(self.handle)

        # Bottom Drawer (Buttons)
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revealer.set_transition_duration(150)
        self.revealer.set_visible(False)

        self.btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.btn_box.set_halign(Gtk.Align.CENTER)
        self.btn_box.set_valign(Gtk.Align.CENTER)
        self.btn_box.set_hexpand(False)
        self.btn_box.set_margin_bottom(4)
        self.btn_box.set_visible(False)

        # Buttons
        # 1. Close
        quit_btn = Gtk.Button()
        quit_btn.add_css_class("overlay-btn")
        img_quit = Gtk.Image.new_from_file(self.get_asset_path("quit.svg"))
        img_quit.set_pixel_size(16)
        quit_btn.set_child(img_quit)
        quit_btn.connect("clicked", self.on_close_request)

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

        # Keyboard shortcuts
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self.on_key_pressed)
        self.add_controller(key_ctrl)

        # GLib timeout for animation
        GLib.timeout_add(self.scroll_speed, self.update_animation)

    def get_asset_path(self, filename):
        # We'll use the assets folder in Project root for now
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", filename)

    @log_function_calls
    def setup_audio(self):
        pipeline_str = "autoaudiosrc ! audioconvert ! level interval=50000000 ! fakesink"
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::element", self.on_level_message)
            # Do not set to PLAYING here, wait for Record button
            self.pipeline.set_state(Gst.State.NULL)
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
            self.current_height += (self.target_height - self.current_height) * 0.4
            h = int(self.current_height)
            self.set_size_request(100, h)
            # Content height is window height minus 4px border (2px top + 2px bottom)
            content_h = max(0, h - 4)
            self.main_box.set_size_request(96, content_h)
            self.canvas.queue_draw()

        for i in range(self.num_bars):
            # Shift bar weights slightly for organic movement
            self.bar_weights[i] = max(0.2, min(1.0, self.bar_weights[i] + random.uniform(-0.05, 0.05)))
            
            # Use audio level + individual weight + jitter
            jitter = random.uniform(0.8, 1.2)
            target = (self.last_audio_level * self.bar_weights[i] * jitter) + 0.05
            
            # Smoothing
            self.levels[i] = self.levels[i] * 0.3 + target * 0.7
            
        self.canvas.queue_draw()
        return True

    def on_draw(self, drawing_area, cr, width, height):
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        thickness, gap, margin_y = 2, 2, 3
        usable_height = height - 2 * margin_y
        
        num_bars = len(self.levels)
        total_bars_width = (num_bars * thickness) + ((num_bars - 1) * gap)
        start_x = (width - total_bars_width) / 2
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
        self.target_height = 48
        self.revealer.set_visible(True)
        self.revealer.set_reveal_child(True)
        self.btn_box.set_visible(True)

    def on_close_request(self, btn):
        self.close()
        self.app.quit()

    def on_hover_leave(self, ctrl):
        if self.revealed:
            self.revealed = False
            self.target_height = 24
            self.revealer.set_reveal_child(False)
            self.revealer.set_visible(False)
            self.btn_box.set_visible(False)

    @log_function_calls
    def on_record_clicked(self, btn):
        self.toggle_recording()

    def on_stop_clicked(self, btn):
        self.toggle_recording()

    def cancel_recording(self):
        try:
            result = subprocess.run(["hyprvoice", "cancel"], capture_output=True, text=True, check=False)
            if result.stdout:
                logging.info(f"hyprvoice: {result.stdout.strip()}")
            if result.stderr:
                logging.error(f"hyprvoice error: {result.stderr.strip()}")
        except Exception as e:
            logging.error(f"Failed to run hyprvoice cancel: {e}")

        # Stop UI and audio pipeline
        self.recording = False
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        
        # Reset UI immediately
        self.record_btn.set_visible(True)
        self.stop_btn.set_visible(False)

    @log_function_calls
    def toggle_recording(self):
        try:
            result = subprocess.run(["hyprvoice", "toggle"], capture_output=True, text=True, check=False)
            if result.stdout:
                logger.info(f"hyprvoice toggle result: {result.stdout.strip()}")
            if result.stderr:
                logger.error(f"hyprvoice toggle error: {result.stderr.strip()}")
        except Exception as e:
            logger.error(f"Failed to run hyprvoice toggle: {e}")

        self.recording = not self.recording
        
        if self.recording:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.PLAYING)
            self.record_btn.set_visible(False)
            self.stop_btn.set_visible(True)
        else:
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
            # Reset levels immediately for a clean stop
            self.last_audio_level = 0.0
            self.levels = [0.05] * len(self.levels)
            self.record_btn.set_visible(True)
            self.stop_btn.set_visible(False)

    def on_preferences_clicked(self, btn):
        win = PreferencesWindow(self)
        win.present()

    def on_key_pressed(self, controller, keyval, keycode, state):
        # Ctrl+E to open preferences
        if keyval == Gdk.KEY_e and (state & Gdk.ModifierType.CONTROL_MASK):
            self.on_preferences_clicked(None)
            return True
        return False

        
