import gi
gi.require_version('Gtk', '4.0')
from gi.repository import Gtk
import datetime
import subprocess

from .config_manager import ConfigManager

class PreferencesWindow(Gtk.Window):
    def __init__(self, parent):
        super().__init__(transient_for=parent)
        self.set_title("Preferences")
        self.set_modal(True)
        self.set_default_size(500, 600)
        
        self.config_manager = ConfigManager()
        full_config = self.config_manager.get_config()
        self.tx_config = full_config.get("transcription", {})
        self.rec_config = full_config.get("recording", {})
        self.inj_config = full_config.get("injection", {})
        self.notif_config = full_config.get("notifications", {})
        self.log_config = full_config.get("logging", {})

        # Main scroller
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.set_child(scrolled)

        # Content Box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        scrolled.set_child(main_box)

        # --- Transcription Section ---
        tx_frame = Gtk.Frame(label="Transcription")
        tx_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        tx_box.set_margin_top(10)
        tx_box.set_margin_bottom(10)
        tx_box.set_margin_start(10)
        tx_box.set_margin_end(10)
        tx_frame.set_child(tx_box)
        main_box.append(tx_frame)

        # Provider
        tx_box.append(Gtk.Label(label="Provider", xalign=0))
        self.provider_entry = Gtk.DropDown.new_from_strings(["openai", "groq-transcription", "groq-translation"])
        current_provider = self.tx_config.get("provider", "openai")
        if current_provider == "openai":
            self.provider_entry.set_selected(0)
        elif current_provider == "groq-transcription":
            self.provider_entry.set_selected(1)
        elif current_provider == "groq-translation":
            self.provider_entry.set_selected(2)
        tx_box.append(self.provider_entry)

        # API Key
        tx_box.append(Gtk.Label(label="API Key", xalign=0))
        self.api_key_entry = Gtk.Entry()
        self.api_key_entry.set_text(self.tx_config.get("api_key", ""))
        self.api_key_entry.set_visibility(False)
        self.api_key_entry.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY, "view-reveal-symbolic")
        self.api_key_entry.connect("icon-press", self.toggle_password_visibility)
        tx_box.append(self.api_key_entry)

        # Language
        tx_box.append(Gtk.Label(label="Language (empty for auto)", xalign=0))
        self.language_entry = Gtk.Entry()
        self.language_entry.set_text(self.tx_config.get("language", ""))
        tx_box.append(self.language_entry)

        # Model
        tx_box.append(Gtk.Label(label="Model", xalign=0))
        self.model_entry = Gtk.Entry()
        self.model_entry.set_text(self.tx_config.get("model", "whisper-1"))
        tx_box.append(self.model_entry)

        # --- Recording Section ---
        rec_frame = Gtk.Frame(label="Recording")
        rec_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        rec_box.set_margin_top(10)
        rec_box.set_margin_bottom(10)
        rec_box.set_margin_start(10)
        rec_box.set_margin_end(10)
        rec_frame.set_child(rec_box)
        main_box.append(rec_frame)

        rec_box.append(Gtk.Label(label="Timeout (e.g. 5m, 30s)", xalign=0))
        self.timeout_entry = Gtk.Entry()
        self.timeout_entry.set_text(self.rec_config.get("timeout", "5m"))
        rec_box.append(self.timeout_entry)

        # --- Injection Section ---
        inj_frame = Gtk.Frame(label="Text Injection")
        inj_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        inj_box.set_margin_top(10)
        inj_box.set_margin_bottom(10)
        inj_box.set_margin_start(10)
        inj_box.set_margin_end(10)
        inj_frame.set_child(inj_box)
        main_box.append(inj_frame)

        inj_box.append(Gtk.Label(label="Mode", xalign=0))
        self.mode_entry = Gtk.DropDown.new_from_strings(["fallback", "clipboard", "type"])
        current_mode = self.inj_config.get("mode", "fallback")
        if current_mode == "fallback":
            self.mode_entry.set_selected(0)
        elif current_mode == "clipboard":
            self.mode_entry.set_selected(1)
        elif current_mode == "type":
            self.mode_entry.set_selected(2)
        inj_box.append(self.mode_entry)

        self.restore_clipboard_switch = Gtk.CheckButton(label="Restore Clipboard after injection")
        self.restore_clipboard_switch.set_active(self.inj_config.get("restore_clipboard", True))
        inj_box.append(self.restore_clipboard_switch)

        # --- Notifications Section ---
        notif_frame = Gtk.Frame(label="Notifications")
        notif_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        notif_box.set_margin_top(10)
        notif_box.set_margin_bottom(10)
        notif_box.set_margin_start(10)
        notif_box.set_margin_end(10)
        notif_frame.set_child(notif_box)
        main_box.append(notif_frame)

        self.notifications_switch = Gtk.CheckButton(label="Enable Desktop Notifications")
        self.notifications_switch.set_active(self.notif_config.get("enabled", True))
        notif_box.append(self.notifications_switch)

        # --- Logging Section ---
        log_frame = Gtk.Frame(label="Logging")
        log_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        log_box.set_margin_top(10)
        log_box.set_margin_bottom(10)
        log_box.set_margin_start(10)
        log_box.set_margin_end(10)
        log_frame.set_child(log_box)
        main_box.append(log_frame)

        log_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        log_row.append(Gtk.Label(label="Enable Debug Logging", xalign=0, hexpand=True))
        self.debug_logging_switch = Gtk.Switch()
        self.debug_logging_switch.set_active(self.log_config.get("debug", False))
        self.debug_logging_switch.set_valign(Gtk.Align.CENTER)
        log_row.append(self.debug_logging_switch)
        log_box.append(log_row)

        # --- Daemon Management Section ---
        daemon_frame = Gtk.Frame(label="Daemon Management")
        daemon_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        daemon_box.set_margin_top(10)
        daemon_box.set_margin_bottom(10)
        daemon_box.set_margin_start(10)
        daemon_box.set_margin_end(10)
        daemon_frame.set_child(daemon_box)
        main_box.append(daemon_frame)

        grid = Gtk.Grid(column_spacing=10, row_spacing=10)
        grid.set_halign(Gtk.Align.CENTER)
        daemon_box.append(grid)

        btn_start = Gtk.Button(label="Start Service")
        btn_start.connect("clicked", self.on_start_clicked)
        grid.attach(btn_start, 0, 0, 1, 1)

        btn_stop = Gtk.Button(label="Stop Service")
        btn_stop.connect("clicked", self.on_stop_clicked)
        grid.attach(btn_stop, 1, 0, 1, 1)

        btn_status = Gtk.Button(label="Check Status")
        btn_status.connect("clicked", self.on_status_clicked)
        grid.attach(btn_status, 0, 1, 1, 1)

        btn_version = Gtk.Button(label="Version")
        btn_version.connect("clicked", self.on_version_clicked)
        grid.attach(btn_version, 1, 1, 1, 1)

        # Output area
        scrolled_out = Gtk.ScrolledWindow()
        scrolled_out.set_min_content_height(150)
        scrolled_out.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        
        self.output_view = Gtk.TextView()
        self.output_view.set_editable(False)
        self.output_view.set_monospace(True)
        self.output_view.set_wrap_mode(Gtk.WrapMode.WORD)
        self.output_buffer = self.output_view.get_buffer()
        scrolled_out.set_child(self.output_view)

        frame_out = Gtk.Frame()
        frame_out.set_child(scrolled_out)
        daemon_box.append(frame_out)

        # --- Save Button ---
        save_btn = Gtk.Button(label="Save Preferences")
        save_btn.add_css_class("suggested-action")
        save_btn.set_margin_top(10)
        save_btn.connect("clicked", self.on_save_clicked)
        main_box.append(save_btn)

    def append_output(self, text):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        end_iter = self.output_buffer.get_end_iter()
        self.output_buffer.insert(end_iter, f"[{timestamp}] {text}\n")
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

    def on_start_clicked(self, btn):
        self.append_output("Starting hyprvoice daemon...")
        try:
            # Re-use Application.start_daemon if possible
            app = self.get_transient_for().app
            app.start_daemon()
            self.append_output("Daemon start command issued.")
        except Exception as e:
            self.append_output(f"Failed to start: {e}")

    def on_stop_clicked(self, btn):
        self.run_command(["hyprvoice", "stop"])

    def on_status_clicked(self, btn):
        self.run_command(["hyprvoice", "status"])

    def on_version_clicked(self, btn):
        self.run_command(["hyprvoice", "version"])

    def toggle_password_visibility(self, entry, icon_pos):
        entry.set_visibility(not entry.get_visibility())

    def on_save_clicked(self, btn):
        updates = {}

        # Transcription
        providers = ["openai", "groq-transcription", "groq-translation"]
        updates["transcription"] = {
            "provider": providers[self.provider_entry.get_selected()],
            "api_key": self.api_key_entry.get_text(),
            "language": self.language_entry.get_text(),
            "model": self.model_entry.get_text()
        }

        # Recording
        updates["recording"] = {
            "timeout": self.timeout_entry.get_text()
        }

        # Injection
        modes = ["fallback", "clipboard", "type"]
        updates["injection"] = {
            "mode": modes[self.mode_entry.get_selected()],
            "restore_clipboard": self.restore_clipboard_switch.get_active()
        }

        # Notifications
        updates["notifications"] = {
            "enabled": self.notifications_switch.get_active()
        }

        # Logging
        updates["logging"] = {
            "debug": self.debug_logging_switch.get_active()
        }
        
        self.config_manager.save_config(updates)
        self.close()
