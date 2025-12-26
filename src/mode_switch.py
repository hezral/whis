# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2025 Adi Hezral <hezral@gmail.com>

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gtk, GObject, Gdk

class ModeSwitch(Gtk.Grid):
    '''Gtk only basic port of https://github.com/elementary/granite/blob/master/lib/Widgets/ModeSwitch.vala'''

    __gtype_name__ = "ModeSwitch"

    active = GObject.Property(type=bool, default=True)
    
    def __init__(self, primary_widget, secondary_widget, primary_widget_callback, secondary_widget_callback, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.primary_widget = primary_widget
        self.secondary_widget = secondary_widget

        self.primary_widget_callback = primary_widget_callback
        self.secondary_widget_callback = secondary_widget_callback
        
        if self.primary_widget is not None:
            # Gtk4 event handling
            ctrl = Gtk.GestureClick()
            ctrl.connect("released", self.on_primary_widget_pressed)
            self.primary_widget.add_controller(ctrl)
            
            self.primary_widget.props.valign = Gtk.Align.CENTER
            self.primary_widget.props.halign = Gtk.Align.END
            self.attach(self.primary_widget, 0, 0, 1, 1)

        if self.secondary_widget is not None:
            ctrl = Gtk.GestureClick()
            ctrl.connect("released", self.on_secondary_widget_pressed)
            self.secondary_widget.add_controller(ctrl)
            
            self.secondary_widget.props.valign = Gtk.Align.CENTER
            self.secondary_widget.props.halign = Gtk.Align.START
            self.attach(self.secondary_widget, 2, 0, 1, 1)
    
        self.switch = Gtk.Switch()
        self.switch.add_css_class("modeswitch")
        self.switch.props.can_focus = False
        self.switch.props.valign = Gtk.Align.CENTER
        self.switch.props.margin_top = 1
        self.switch.set_size_request(32, -1)
        self.attach(self.switch, 1, 0, 1, 1)

        self.props.column_spacing = 6
        self.props.margin_top = 6
        self.props.margin_end = 6 # margin_right is deprecated/removed in Gtk4 favor of margin_end

    def on_primary_widget_pressed(self, gesture, n_press, x, y):
        self.active = False
        if self.primary_widget_callback is not None:
            self.primary_widget_callback()

    def on_secondary_widget_pressed(self, gesture, n_press, x, y):
        self.active = True
        if self.secondary_widget_callback is not None:
            self.secondary_widget_callback()
