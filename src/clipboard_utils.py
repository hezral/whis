# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 Adi Hezral <hezral@gmail.com>

import gi
gi.require_version('Gdk', '4.0')
from gi.repository import Gio, GLib, Gdk
import logging

logger = logging.getLogger(__name__)

class ClipboardUtils:
    def __init__(self):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.session_path = None

    def _create_session(self):
        try:
            res = self.bus.call_sync(
                "org.gnome.Mutter.RemoteDesktop",
                "/org/gnome/Mutter/RemoteDesktop",
                "org.gnome.Mutter.RemoteDesktop",
                "CreateSession",
                None,
                GLib.VariantType.new("(o)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            self.session_path = res.unpack()[0]
            logger.debug(f"Mutter session path: {self.session_path}")
            
            # Start the session
            self.bus.call_sync(
                "org.gnome.Mutter.RemoteDesktop",
                self.session_path,
                "org.gnome.Mutter.RemoteDesktop.Session",
                "Start",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            return False

    def simulate_ctrl_v(self):
        """Simulates Ctrl+V and Shift+Ctrl+V"""
        if not self._create_session():
            return

        try:
            control_l = Gdk.keyval_from_name("Control_L")
            shift_l = Gdk.keyval_from_name("Shift_L")
            v_key = Gdk.keyval_from_name("v")
            
            # 1. Simulate Ctrl+V
            logger.debug("Simulating Ctrl+V")
            self._notify_keysym(control_l, True)
            self._notify_keysym(v_key, True)
            self._notify_keysym(v_key, False)
            self._notify_keysym(control_l, False)
            
            # Small delay to ensure the OS/App processes the first paste
            GLib.usleep(50000) # 50ms

            # 2. Simulate Shift+Ctrl+V
            logger.debug("Simulating Shift+Ctrl+V")
            self._notify_keysym(control_l, True)
            self._notify_keysym(shift_l, True)
            self._notify_keysym(v_key, True)
            self._notify_keysym(v_key, False)
            self._notify_keysym(shift_l, False)
            self._notify_keysym(control_l, False)
            
            logger.info("Ctrl+V and Shift+Ctrl+V simulated via Mutter.")
        except Exception as e:
            logger.error(f"Error during paste simulation: {e}")
        finally:
            self._stop_session()

    def _notify_keysym(self, keysym, state):
        """Sends a keysym notification to the Mutter session."""
        self.bus.call_sync(
            "org.gnome.Mutter.RemoteDesktop",
            self.session_path,
            "org.gnome.Mutter.RemoteDesktop.Session",
            "NotifyKeyboardKeysym",
            GLib.Variant("(ub)", [keysym, state]),
            None,
            Gio.DBusCallFlags.NONE,
            -1,
            None
        )

    def _stop_session(self):
        """Stops the Mutter RemoteDesktop session."""
        if not self.session_path:
            return
        try:
            self.bus.call_sync(
                "org.gnome.Mutter.RemoteDesktop",
                self.session_path,
                "org.gnome.Mutter.RemoteDesktop.Session",
                "Stop",
                None,
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None
            )
            logger.debug("Mutter session stopped.")
        except Exception as e:
            logger.error(f"Error stopping Mutter session: {e}")
        self.session_path = None
