#!/usr/bin/env python3
import gi
import sys
import os
import math
import random

gi.require_version('Gtk', '4.0')
gi.require_version('Gdk', '4.0')
gi.require_version('Gst', '1.0')
from gi.repository import Gtk, Gdk, Gst, GLib, GObject
import cairo

class SoundWavePrototype(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="com.github.hezral.whis.prototype")
        Gst.init(None)
        self.levels = [0.05] * 15
        self.last_audio_level = 0.0
        self.pipeline = None
        # History for sliding-window normalization
        self.level_history = [-100.0] * 50
        self.sensitivity = 0.5  # Control the height multiplier
        self.scroll_speed = 40  # Propagation speed in ms (lower is faster)
        # For window expansion animation
        self.target_height = 32
        self.current_height = 32
        self.revealed = False

    def do_activate(self):
        self.win = Gtk.ApplicationWindow(application=self)
        self.win.set_decorated(False)
        self.win.set_resizable(False)
        # Make the window background transparent if possible
        self.win.set_name("pill-window")
        self.win.set_default_size(100, 32)
        
        provider = Gtk.CssProvider()
        provider.load_from_data(b"""
            #pill-window {
                background-color: rgba(0, 0, 0, 0.5);
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
            .top-quit {
                margin-top: 3px;
                margin-left: 3px;
            }
        """)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Main Layout: Vertical Box
        self.main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.main_box.set_name("main-container")

        # Top: Soundwave Area (Window Handle for moving)
        self.canvas = Gtk.DrawingArea()
        self.canvas.set_draw_func(self.on_draw)
        self.canvas.set_size_request(-1, 32)
        
        self.handle = Gtk.WindowHandle()
        self.handle.set_child(self.canvas)
        self.main_box.append(self.handle)

        # Bottom: Button Area (Revealer)
        self.revealer = Gtk.Revealer()
        self.revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revealer.set_transition_duration(300)

        # Button Box
        self.btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.btn_box.set_halign(Gtk.Align.CENTER)
        self.btn_box.set_valign(Gtk.Align.CENTER)
        # self.btn_box.set_margin_top(4)
        self.btn_box.set_margin_bottom(8)

        play_btn = Gtk.Button()
        play_btn.add_css_class("overlay-btn")
        # Record icon (Red circle)
        img_record = Gtk.Image.new_from_file("/home/adi/Projects/whis/assets/record.svg")
        img_record.set_pixel_size(16)
        play_btn.set_child(img_record)
        
        stop_btn = Gtk.Button()
        stop_btn.add_css_class("overlay-btn")
        img_stop = Gtk.Image.new_from_file("/home/adi/Projects/whis/assets/stop.svg")
        img_stop.set_pixel_size(16)
        stop_btn.set_child(img_stop)
        
        pref_btn = Gtk.Button()
        pref_btn.add_css_class("overlay-btn")
        img_pref = Gtk.Image.new_from_file("/home/adi/Projects/whis/assets/prefs.svg")
        img_pref.set_pixel_size(16)
        pref_btn.set_child(img_pref)
        
        self.quit_btn = Gtk.Button()
        self.quit_btn.add_css_class("overlay-btn")
        self.quit_btn.add_css_class("top-quit")
        img_quit = Gtk.Image.new_from_file("/home/adi/Projects/whis/assets/quit.svg")
        img_quit.set_pixel_size(16)
        self.quit_btn.set_child(img_quit)
        self.quit_btn.connect("clicked", self.on_quit_clicked)
        self.quit_btn.set_halign(Gtk.Align.START)
        self.quit_btn.set_valign(Gtk.Align.START)
        self.quit_btn.set_visible(False)

        self.btn_box.append(play_btn)
        self.btn_box.append(stop_btn)
        self.btn_box.append(pref_btn)
        # Quit button removed from bottom Tray

        self.revealer.set_child(self.btn_box)
        self.main_box.append(self.revealer)

        # Root Overlay to allow absolute positioning of Quit button
        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self.main_box)
        self.overlay.add_overlay(self.quit_btn)
        
        # Click to reveal (Soundwave handle only)
        click_gesture = Gtk.GestureClick()
        click_gesture.connect("pressed", self.on_window_clicked)
        self.handle.add_controller(click_gesture)

        # Hover out to hide (Whole window)
        motion_ctrl = Gtk.EventControllerMotion()
        motion_ctrl.connect("leave", self.on_hover_leave)
        self.main_box.add_controller(motion_ctrl)

        self.win.set_child(self.overlay)
        self.setup_audio()
        self.win.present()

        # Update loop for animation
        GLib.timeout_add(self.scroll_speed, self.update_animation)

    def on_window_clicked(self, gesture, n_press, x, y):
        # Reveal on click
        self.revealed = True
        self.target_height = 64
        self.revealer.set_reveal_child(True)
        self.quit_btn.set_visible(True)

    def on_hover_leave(self, ctrl):
        # Hide on mouse leave
        if self.revealed:
            self.revealed = False
            self.target_height = 32
            self.revealer.set_reveal_child(False)
            self.quit_btn.set_visible(False)

    def on_quit_clicked(self, btn):
        print("Quit button clicked!", flush=True)
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        self.quit()

    def setup_audio(self):
        # Using autoaudiosrc but with audioconvert for robustness
        pipeline_str = "autoaudiosrc ! audioconvert ! level interval=50000000 ! fakesink"
        try:
            self.pipeline = Gst.parse_launch(pipeline_str)
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::element", self.on_level_message)
            bus.connect("message::error", self.on_error_message)
            
            self.pipeline.set_state(Gst.State.PLAYING)
            print(f"GStreamer pipeline started: {pipeline_str}", flush=True)
        except Exception as e:
            print(f"Failed to setup audio: {e}", flush=True)

    def on_error_message(self, bus, message):
        err, debug = message.parse_error()
        print(f"GStreamer Error: {err.message}", flush=True)

    def on_level_message(self, bus, message):
        if message.get_structure().get_name() == "level":
            rms = message.get_structure().get_value("rms")
            avg_rms = sum(rms) / len(rms)
            
            # 1. Update sliding window history
            self.level_history.pop(0)
            self.level_history.append(avg_rms)
            
            # 2. Get current range
            h_min = min(self.level_history)
            h_max = max(self.level_history)
            
            # 3. Normalize current value (min spread of 1dB)
            spread = max(1, h_max - h_min)
            normalized = (avg_rms - h_min) / spread
            normalized = max(0, min(1, normalized))
            
            # 4. Smooth audio level for visualization
            self.last_audio_level = self.last_audio_level * 0.4 + normalized * 0.6

    def update_animation(self):
        # Smooth window height expansion
        if abs(self.target_height - self.current_height) > 0.5:
            # If expanding UP, we might need to nudge the window pos
            # (Move is often blocked by compositors, but we try)
            # height_diff = (self.target_height - self.current_height) * 0.2
            self.current_height += (self.target_height - self.current_height) * 0.2
            self.win.set_default_size(100, int(self.current_height))
            
            # Force size update 
            self.canvas.queue_draw()

        # Shift everything left to create propagation effect
        self.levels.pop(0)
        
        # Base jitter for "alive" feel
        jitter = random.uniform(0.01, 0.03)
        # Combine audio level and jitter
        new_val = (self.last_audio_level * 0.9) + jitter
        self.levels.append(new_val)
        
        self.canvas.queue_draw()
        return True

    def on_draw(self, drawing_area, cr, width, height):
        # Draw background pill shape ONLY for the soundwave area
        # Note: height here is the height of the DrawingArea (32px)
        cr.set_source_rgba(0.05, 0.05, 0.05, 0.0) # Transparent canvas background
        cr.paint()

        # Draw sound wave
        thickness = 2
        gap = 2
        margin = 5
        usable_width = width - 2 * margin
        usable_height = height - 2 * margin
        
        # Dynamically calculate number of bars that fit
        num_bars = int((usable_width + gap) // (thickness + gap))
        
        # Synchronize self.levels size
        if len(self.levels) != num_bars:
            if len(self.levels) < num_bars:
                self.levels = [0.05] * (num_bars - len(self.levels)) + self.levels
            else:
                self.levels = self.levels[-num_bars:]

        # Calculate start_x to center the group of bars precisely
        total_bars_width = (num_bars * thickness) + ((num_bars - 1) * gap)
        start_x = margin + (usable_width - total_bars_width) / 2
        mid_y = height / 2

        for i, level in enumerate(self.levels):
            x = start_x + (i * (thickness + gap)) + (thickness / 2)
            # Use a good portion of the height for the bars, scaled by sensitivity
            bar_height = (level * self.sensitivity * (usable_height - 2)) + 2
            # White bars with high transparency
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.50)
            cr.set_line_width(thickness)
            cr.set_line_cap(1) # Round caps
            
            cr.move_to(x, mid_y - bar_height / 2)
            cr.line_to(x, mid_y + bar_height / 2)
            cr.stroke()

if __name__ == "__main__":
    app = SoundWavePrototype()
    app.run(sys.argv)
