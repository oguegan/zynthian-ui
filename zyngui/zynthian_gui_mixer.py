#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Audio Mixer
#
# Copyright (C) 2015-2020 Fernando Moyano <jofemodo@zynthian.org>
# Copyright (C) 2015-2021 Brian Walton <brian@riban.co.uk>
#
#******************************************************************************
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation; either version 2 of
# the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# For a full copy of the GNU General Public License see the LICENSE.txt file.
#
#******************************************************************************

import sys
import logging
import tkinter
from time import monotonic
from tkinter import font as tkFont
from PIL import Image, ImageTk
import liblo
import os

# Zynthian specific modules
from zyngine import zynthian_controller
import zyngine
from . import zynthian_gui_base
from . import zynthian_gui_config
from . import zynthian_gui_controller
from zynlibs.zynmixer import *
from zyncoder.zyncore import lib_zyncore

ENC_LAYER		= 0
ENC_BACK		= 1
ENC_SNAPSHOT	= 2
ENC_SELECT		= 3

MAX_NUM_CHANNELS = 16

#------------------------------------------------------------------------------
# Zynthian Main Mixbus Layer Class
# This is a dummy class to provide a stub for the main mixbus strip's layer
#------------------------------------------------------------------------------
class zynthian_gui_mixer_main_layer():
	def __init__(self):
		self.midi_chan = MAX_NUM_CHANNELS


#------------------------------------------------------------------------------
# Zynthian Mixer Strip Class
# This provides a UI element that represents a mixer strip, one used per chain
#------------------------------------------------------------------------------

class zynthian_gui_mixer_strip():
	# Initialise mixer strip object
	#	canvas: Canvas on which to draw fader
	#	x: Horizontal coordinate of left of fader
	#	y: Vertical coordinate of top of fader
	#	width: Width of fader
	#	height: Height of fader
	#	layer: Layer object associated with strip (None to disable strip)
	#	on_select_cb: Function to call when fader is selected (must accept layer object as parameter)
	#	on_edit_cb: Function to call when mixer strip edit is requested
	#	refresh_all_pending_cb: Function to set flag indicating refresh all mixer strips required

	mute_color = zynthian_gui_config.color_on
	solo_color = "dark green"

	def __init__(self, canvas, x, y, width, height, layer, on_select_cb, on_edit_cb, on_fader_cb, refresh_all_pending_cb):
		self.main_canvas = canvas
		self.x = x
		self.y = y
		self.width = width
		self.height = height
		self.hidden = False
		self.layer = layer
		self.redraw_controls_flag = False

		if not layer:
			self.hidden = True

		self.on_select_cb = on_select_cb
		self.on_edit_cb = on_edit_cb
		self.on_fader_cb = on_fader_cb
		self.refresh_all_pending_cb = refresh_all_pending_cb

		self.button_height = int(self.height * 0.1)
		self.legend_height = int(self.height * 0.08)
		self.balance_height = int(self.height * 0.03)
		self.fader_height = self.height - self.balance_height - self.legend_height - 2 * self.button_height
		self.fader_bottom = self.height - self.legend_height - self.balance_height
		self.fader_top = self.fader_bottom - self.fader_height
		fader_centre = x + width * 0.5
		self.balance_top = self.fader_bottom
		self.balance_control_centre = int(self.width / 2)
		self.balance_control_width = int(self.width / 4) # Width of each half of balance control

		#Digital Peak Meter (DPM) parameters
		self.dpm_rangedB = 50 # Lowest meter reading in -dBFS
		self.dpm_highdB = 10 # Start of yellow zone in -dBFS
		self.dpm_overdB = 3  # Start of red zone in -dBFS
		self.dpm_high = 1 - self.dpm_highdB / self.dpm_rangedB
		self.dpm_over = 1 - self.dpm_overdB / self.dpm_rangedB
		self.dpm_scale_lm = int(self.dpm_high * self.fader_height)
		self.dpm_scale_lh = int(self.dpm_over * self.fader_height)

		self.dpm_width = int(self.width / 10)
		self.dpm_a_x = x + self.width - self.dpm_width * 2 - 2
		self.dpm_a_y = self.fader_bottom
		self.dpm_b_x = x + self.width - self.dpm_width - 1
		self.dpm_b_y = self.fader_bottom
		self.dpm_zero_y = self.fader_bottom - self.fader_height * self.dpm_high
		self.fader_width = self.width - self.dpm_width * 2 - 2

		self.drag_start = None

		# Default style
		self.fader_bg_color = zynthian_gui_config.color_bg
		#self.fader_color = zynthian_gui_config.color_panel_hl
		#self.fader_color_hl = zynthian_gui_config.color_low_on
		self.fader_color = zynthian_gui_config.color_off
		self.fader_color_hl = zynthian_gui_config.color_on
		self.legend_txt_color = zynthian_gui_config.color_tx
		self.button_bgcol = zynthian_gui_config.color_panel_bg
		self.button_txcol = zynthian_gui_config.color_tx
		self.left_color = "red"
		self.right_color = "dark green"
		self.low_color = "dark green"
		self.medium_color = "#AAAA00" # yellow
		self.high_color = "dark red"

		#font_size = int(0.5 * self.legend_height)
		font_size = int(0.25 * self.width)
		font = (zynthian_gui_config.font_family, font_size)
		font_fader = (zynthian_gui_config.font_family, font_size-1)

		'''
		Create GUI elements
		Tags:
			strip:X All elements within the fader strip used to show/hide strip
			fader:X Elements used for fader drag
			X is the id of this fader's background
		'''

		# Fader
		self.fader_bg = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_bg_color, width=0)
		self.main_canvas.itemconfig(self.fader_bg, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)))
		self.fader = self.main_canvas.create_rectangle(x, self.fader_top, x + self.width, self.fader_bottom, fill=self.fader_color, width=0, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.legend = self.main_canvas.create_text(x, self.fader_bottom - 2, fill=self.legend_txt_color, text="", tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg)), angle=90, anchor="nw", font=font_fader)

		# DPM
		self.dpm_h_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_m_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_l_a = self.main_canvas.create_rectangle(x + self.width - 8, self.fader_bottom, x + self.width - 5, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_h_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.high_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_m_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_l_b = self.main_canvas.create_rectangle(x + self.width - 4, self.fader_bottom, x + self.width - 1, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.dpm_hold_a = self.main_canvas.create_rectangle(self.dpm_a_x, self.fader_bottom, self.dpm_a_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), state="hidden")
		self.dpm_hold_b = self.main_canvas.create_rectangle(self.dpm_b_x, self.fader_bottom, self.dpm_b_x + self.dpm_width, self.fader_bottom, width=0, fill=self.low_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), state="hidden")

		# 0dB line
		self.main_canvas.create_line(self.dpm_a_x, self.dpm_zero_y, x + self.width, self.dpm_zero_y, fill=self.medium_color, tags=("fader:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))

		# Solo button
		self.solo = self.main_canvas.create_rectangle(x, 0, x + self.width, self.button_height, fill=self.button_bgcol, width=0, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.main_canvas.create_text(x + self.width / 2, self.button_height * 0.5, text="solo", fill=self.button_txcol, tags=("solo_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), font=font)

		# Mute button
		self.mute = self.main_canvas.create_rectangle(x, self.button_height, x + self.width, self.button_height * 2, fill=self.button_bgcol, width=0, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.main_canvas.create_text(x + self.width / 2, self.button_height * 1.5, text="mute", fill=self.button_txcol, tags=("mute_button:%s"%(self.fader_bg), "strip:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)), font=font)

		# Legend strip at bottom of screen
		self.legend_strip_bg = self.main_canvas.create_rectangle(x, self.height - self.legend_height, x + self.width, self.height, width=0, tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)))
		self.legend_strip_txt = self.main_canvas.create_text(int(fader_centre), self.height - self.legend_height / 2, fill=self.legend_txt_color, text="-", tags=("strip:%s"%(self.fader_bg),"legend_strip:%s"%(self.fader_bg)), font=font)

		# Balance indicator
		self.balance_left = self.main_canvas.create_rectangle(x, self.fader_top, int(fader_centre - 0.5), self.fader_top + self.balance_height, fill=self.left_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))
		self.balance_right = self.main_canvas.create_rectangle(int(fader_centre + 0.5), self.fader_top, self.width, self.fader_top + self.balance_height , fill=self.right_color, width=0, tags=("strip:%s"%(self.fader_bg), "balance:%s"%(self.fader_bg), "audio_strip:%s"%(self.fader_bg)))

		self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_fader_press)
		self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<B1-Motion>", self.on_fader_motion)
		if os.environ.get("ZYNTHIAN_UI_ENABLE_CURSOR") == "1":
			self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-4>", self.on_fader_wheel_up)
			self.main_canvas.tag_bind("fader:%s"%(self.fader_bg), "<Button-5>", self.on_fader_wheel_down)
			self.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-4>", self.on_balance_wheel_up)
			self.main_canvas.tag_bind("balance:%s"%(self.fader_bg), "<Button-5>", self.on_balance_wheel_down)
			#self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-4>", self.on_balance_wheel_up)
			#self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<Button-5>", self.on_balance_wheel_down)
		self.main_canvas.tag_bind("mute_button:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("mute_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("solo_button:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("solo_button:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_solo_release)
		self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonPress-1>", self.on_strip_press)
		self.main_canvas.tag_bind("legend_strip:%s"%(self.fader_bg), "<ButtonRelease-1>", self.on_strip_release)

		self.draw()


	# Function to hide mixer strip
	def hide(self):
		self.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state="hidden")
		self.hidden = True


	# Function to show mixer strip
	def show(self):
		self.main_canvas.itemconfig("strip:%s"%(self.fader_bg), state="normal")
		try:
			if self.layer.engine.type == "MIDI Tool":
				self.main_canvas.itemconfig("audio_strip:%s"%(self.fader_bg), state="hidden")
		except:
			pass
		self.hidden = False
		self.draw()


	# Function to draw mixer strip
	def draw(self):
		if self.hidden or self.layer is None:
			return

		self.main_canvas.itemconfig(self.legend, text="")
		self.main_canvas.coords(self.fader_bg_color, self.x, self.fader_top, self.x + self.width, self.fader_bottom)
		if isinstance(self.layer,  zynthian_gui_mixer_main_layer):
			self.main_canvas.itemconfig(self.legend_strip_txt, text="Main")
			self.main_canvas.itemconfig(self.legend, text="Main")
		else:
			self.main_canvas.itemconfig(self.legend_strip_txt, text=self.layer.midi_chan + 1)
			self.main_canvas.itemconfig(self.legend, text="%s\n%s"%(self.layer.engine.name, self.layer.preset_name), state="normal")

		try:
			if self.layer.engine.type == "MIDI Tool":
				return
		except:
			pass

		self.draw_dpm()
		self.draw_controls()


	# Function to draw the DPM level meter for a mixer strip
	def draw_dpm(self):
		if self.hidden or self.layer.midi_chan is None:
			return

		# Set color
		if zynmixer.get_mono(self.layer.midi_chan):
			self.main_canvas.itemconfig(self.dpm_l_a, fill="gray80")
			self.main_canvas.itemconfig(self.dpm_l_b, fill="gray80")
		else:
			self.main_canvas.itemconfig(self.dpm_l_a, fill=self.low_color)
			self.main_canvas.itemconfig(self.dpm_l_b, fill=self.low_color)
		# Get audio peaks from zynmixer
		signal = max(0, 1 + zynmixer.get_dpm(self.layer.midi_chan,0) / self.dpm_rangedB)
		llA = int(min(signal, self.dpm_high) * self.fader_height)
		lmA = int(min(signal, self.dpm_over) * self.fader_height)
		lhA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm(self.layer.midi_chan,1) / self.dpm_rangedB)
		llB = int(min(signal, self.dpm_high) * self.fader_height)
		lmB = int(min(signal, self.dpm_over) * self.fader_height)
		lhB = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.layer.midi_chan,0) / self.dpm_rangedB)
		lholdA = int(min(signal, 1) * self.fader_height)
		signal = max(0, 1 + zynmixer.get_dpm_hold(self.layer.midi_chan,1) / self.dpm_rangedB)
		lholdB = int(min(signal, 1) * self.fader_height)

		# Draw left meter
		self.main_canvas.coords(self.dpm_l_a,(self.dpm_a_x, self.dpm_a_y, self.dpm_a_x + self.dpm_width, self.dpm_a_y - llA))
		self.main_canvas.itemconfig(self.dpm_l_a, state='normal')

		if lmA >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lm, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lmA))
			self.main_canvas.itemconfig(self.dpm_m_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_a, state="hidden")

		if lhA >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_a,(self.dpm_a_x, self.dpm_a_y - self.dpm_scale_lh, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lhA))
			self.main_canvas.itemconfig(self.dpm_h_a, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_a, state="hidden")

		self.main_canvas.coords(self.dpm_hold_a,(self.dpm_a_x, self.dpm_a_y - lholdA, self.dpm_a_x + self.dpm_width, self.dpm_a_y - lholdA - 1))
		if lholdA >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FF0000")
		elif lholdA >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#FFFF00")
		elif lholdA > 0:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_a, state="hidden")

		# Draw right meter
		self.main_canvas.coords(self.dpm_l_b,(self.dpm_b_x, self.dpm_b_y, self.dpm_b_x + self.dpm_width, self.dpm_b_y - llB))
		self.main_canvas.itemconfig(self.dpm_l_b, state='normal')

		if lmB >= self.dpm_scale_lm:
			self.main_canvas.coords(self.dpm_m_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lm, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lmB))
			self.main_canvas.itemconfig(self.dpm_m_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_m_b, state="hidden")

		if lhB >= self.dpm_scale_lh:
			self.main_canvas.coords(self.dpm_h_b,(self.dpm_b_x, self.dpm_b_y - self.dpm_scale_lh, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lhB))
			self.main_canvas.itemconfig(self.dpm_h_b, state="normal")
		else:
			self.main_canvas.itemconfig(self.dpm_h_b, state="hidden")

		self.main_canvas.coords(self.dpm_hold_b,(self.dpm_b_x, self.dpm_b_y - lholdB, self.dpm_b_x + self.dpm_width, self.dpm_b_y - lholdB - 1))
		if lholdB >= self.dpm_scale_lh:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FF0000")
		elif lholdB >= self.dpm_scale_lm:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#FFFF00")
		elif lholdB > 0:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="normal", fill="#00FF00")
		else:
			self.main_canvas.itemconfig(self.dpm_hold_b, state="hidden")


	# Function to draw the UI controls for a mixer strip
	def draw_controls(self):
		if self.hidden or self.layer.midi_chan is None:
			return

		self.main_canvas.coords(self.fader, self.x, self.fader_top + self.fader_height * (1 - zynmixer.get_level(self.layer.midi_chan)), self.x + self.fader_width, self.fader_bottom)

		color = self.button_bgcol
		if zynmixer.get_mute(self.layer.midi_chan):
			color = self.mute_color
		self.main_canvas.itemconfig(self.mute, fill=color)
		color = self.button_bgcol
		if zynmixer.get_solo(self.layer.midi_chan):
			color = self.solo_color
		self.main_canvas.itemconfig(self.solo, fill=color)

		balance = zynmixer.get_balance(self.layer.midi_chan)
		if balance > 0:
			self.main_canvas.coords(self.balance_left,
				self.x + balance * self.width / 2, self.balance_top,
				self.x + self.width / 2, self.balance_top + self.balance_height)
			self.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width, self.balance_top + self.balance_height)
		else:
			self.main_canvas.coords(self.balance_left,
				self.x, self.balance_top,
				self.x + self.width / 2, self.balance_top + self. balance_height)
			self.main_canvas.coords(self.balance_right,
				self.x + self.width / 2, self.balance_top,
				self.x + self.width * balance / 2 + self.width, self.balance_top + self.balance_height)

		self.redraw_controls_flag = False


	# Function to redraw, if needed, the UI controls for a mixer strip
	def redraw_controls(self, force=False):
		if self.redraw_controls_flag or force:
			self.draw_controls()
			return True
		return False


	# Function to flag redrawing of UI controls for a mixer strip
	def set_redraw_controls(self, flag = True):
		self.redraw_controls_flag = flag


	#--------------------------------------------------------------------------
	# Mixer Strip functionality
	#--------------------------------------------------------------------------

	# Function to set fader colors
	# fg: Fader foreground color
	# bg: Fader background color (optional - Default: Do not change background color)
	def set_fader_color(self, fg, bg=None):
		self.main_canvas.itemconfig(self.fader, fill=fg)
		if bg:
			self.main_canvas.itemconfig(self.fader_bg_color, fill=bg)


	# Function to set layer associated with mixer strip
	#	layer: Layer object
	def set_layer(self, layer):
		self.layer = layer
		if layer is None:
			self.hide()
		else:
			self.show()


	# Function to set volume values
	#	value: Volume value (0..1)
	def set_volume(self, value):
		if self.layer is None:
			return
		if value < 0:
			value = 0
		elif value > 1:
			value = 1
		zynmixer.set_level(self.layer.midi_chan, value)
		self.redraw_controls_flag = True


	# Function to set balance values
	#	value: Balance value (-1..1)
	def set_balance(self, value):
		if self.layer is None:
			return
		if value < -1:
			value = -1
		elif value > 1:
			value = 1
		zynmixer.set_balance(self.layer.midi_chan, value)
		self.redraw_controls_flag = True


	# Function to reset volume
	def reset_volume(self):
		if self.layer is None:
			return
		zynmixer.set_level(self.layer.midi_chan, 0.8)
		self.redraw_controls_flag = True


	# Function to reset balance
	def reset_balance(self):
		if self.layer is None:
			return
		zynmixer.set_balance(self.layer.midi_chan, 0)
		self.redraw_controls_flag = True


	# Function to set mute
	#	value: Mute value (True/False)
	def set_mute(self, value):
		if self.layer is None:
			return
		zynmixer.set_mute(self.layer.midi_chan, value)
		self.redraw_controls_flag = True


	# Function to set solo
	#	value: Solo value (True/False)
	def set_solo(self, value):
		if self.layer is None:
			return
		zynmixer.set_solo(self.layer.midi_chan, value)
		self.redraw_controls_flag = True
		self.refresh_all_pending_cb()


	# Function to toggle mono
	#	value: Mono value (True/False)
	def set_mono(self, value):
		if self.layer is None:
			return
		zynmixer.set_mono(self.layer.midi_chan, value)
		self.redraw_controls_flag = True


	# Function to toggle mute
	def toggle_mute(self):
		if self.layer is None:
			return
		zynmixer.toggle_mute(self.layer.midi_chan)
		self.redraw_controls_flag = True


	# Function to toggle solo
	def toggle_solo(self):
		if self.layer is None:
			return
		zynmixer.toggle_solo(self.layer.midi_chan)
		self.redraw_controls_flag = True
		self.refresh_all_pending_cb()


	# Function to toggle mono
	def toggle_mono(self):
		if self.layer is None:
			return
		zynmixer.toggle_mono(self.layer.midi_chan)
		self.redraw_controls_flag = True


	#--------------------------------------------------------------------------
	# UI event management
	#--------------------------------------------------------------------------

	# Function to handle fader press
	#	event: Mouse event
	def on_fader_press(self, event):
		self.drag_start = event
		self.on_select_cb(self.layer)


	# Function to handle fader drag
	#	event: Mouse event
	def on_fader_motion(self, event):
		if self.layer is None:
			return
		level = zynmixer.get_level(self.layer.midi_chan) + (self.drag_start.y - event.y) / self.fader_height
		self.drag_start = event
		self.set_volume(level)
		self.redraw_controls()
		self.on_fader_cb()


	# Function to handle mouse wheel down over fader
	#	event: Mouse event
	def on_fader_wheel_down(self, event):
		if self.layer is None:
			return "break"
		self.set_volume(zynmixer.get_level(self.layer.midi_chan) - 0.02)
		self.redraw_controls()
		self.on_fader_cb()
		return "break"


	# Function to handle mouse wheel up over fader
	#	event: Mouse event
	def on_fader_wheel_up(self, event):
		if self.layer is None:
			return "break"
		self.set_volume(zynmixer.get_level(self.layer.midi_chan) + 0.02)
		self.redraw_controls()
		self.on_fader_cb()
		return "break"


	# Function to handle mouse wheel down over balance
	#	event: Mouse event
	def on_balance_wheel_down(self, event):
		if self.layer is None:
			return
#		self.on_select_cb(self.layer)
		self.set_balance(zynmixer.get_balance(self.layer.midi_chan) - 0.02)
		self.redraw_controls()


	# Function to handle mouse wheel up over balance
	#	event: Mouse event
	def on_balance_wheel_up(self, event):
		if self.layer is None:
			return
#		self.on_select_cb(self.layer)
		self.set_balance(zynmixer.get_balance(self.layer.midi_chan) + 0.02)
		self.redraw_controls()


	# Function to handle mixer strip press
	#	event: Mouse event
	def on_strip_press(self, event):
		if self.layer is None:
			return
		self.press_time = monotonic()
		self.on_select_cb(self.layer)


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				self.on_edit_cb()
				return
		self.toggle_mute()
		self.redraw_controls()


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4:
				self.on_edit_cb()
				return
		self.toggle_solo()


	# Function to handle legend strip release
	def on_strip_release(self, event):
		if self.press_time:
			delta = monotonic() - self.press_time
			self.press_time = None
			if delta > 0.4 and not isinstance(self.layer, zynthian_gui_mixer_main_layer):
				zynthian_gui_config.zyngui.screens['layer'].select(self.layer.midi_chan)
				zynthian_gui_config.zyngui.screens['layer_options'].reset()
				zynthian_gui_config.zyngui.show_modal('layer_options')
				return
		if self.layer is not None and not isinstance(self.layer, zynthian_gui_mixer_main_layer):
			layer = zynthian_gui_config.zyngui.screens['layer'].get_root_layer_by_midi_chan(self.layer.midi_chan)
			if layer:
				zynthian_gui_config.zyngui.set_curlayer(layer)
				zynthian_gui_config.zyngui.layer_control(layer)


#------------------------------------------------------------------------------
# Zynthian Mixer GUI Class
#------------------------------------------------------------------------------

class zynthian_gui_mixer(zynthian_gui_base.zynthian_gui_base):

	def __init__(self):
		super().__init__()

		# Geometry vars
		self.width=zynthian_gui_config.display_width
		self.height=zynthian_gui_config.body_height

		self.number_layers = 0 # Quantity of layers
		visible_chains = zynthian_gui_config.visible_mixer_strips # Maximum quantity of mixer strips to display (Defines strip width. Main always displayed.)
		if visible_chains < 1:
			# Automatic sizing if not defined in config 
			if self.width <= 400: visible_chains = 4
			elif self.width <= 600: visible_chains = 8
			elif self.width <= 800: visible_chains = 10
			elif self.width <= 1024: visible_chains = 12
			elif self.width <= 1280: visible_chains = 14
			else: visible_chains = 16

		self.fader_width = (self.width - 6 ) / (visible_chains + 1)
		self.legend_height = self.height * 0.05
		self.edit_height = self.height * 0.1

		self.fader_height = self.height - self.edit_height - self.legend_height - 2
		self.fader_bottom = self.height - self.legend_height
		self.fader_top = self.fader_bottom - self.fader_height
		self.balance_control_height = self.fader_height * 0.1
		self.balance_top = self.fader_top
		self.balance_control_width = self.width / 4 # Width of each half of balance control
		self.balance_control_centre = self.fader_width + self.balance_control_width

		# Arrays of GUI elements for mixer strips - Chains + Main
		self.visible_mixer_strips = [None] * visible_chains
		self.selected_chain_index = None
		self.mixer_strip_offset = 0 # Index of first mixer strip displayed on far left
		self.selected_layer = None

		self.redraw_pending = False

		self.press_time = None

		self.edit_chain_index = None # Index of the chain being edited in edit mode
		self.mode = 1 # 1:Mixer, 0:Edit #TODO: Is there a better way to implement touchscreen editing?

		# Fader Canvas
		self.main_canvas = tkinter.Canvas(self.main_frame,
			height=self.height,
			width=self.width,
			bd=0, highlightthickness=0,
			bg = zynthian_gui_config.color_panel_bg)
		self.main_canvas.grid()

		# Mixer strip selection highlight
		color_selhl = zynthian_gui_config.color_on
		self.selection_highlight = self.main_canvas.create_rectangle(0,0,0,0, outline=color_selhl, fill=color_selhl, width=1)

		# Create mixer strip UI objects
		for chain in range(len(self.visible_mixer_strips)):
			self.visible_mixer_strips[chain] = zynthian_gui_mixer_strip(self.main_canvas, 1 + self.fader_width * chain, 0, self.fader_width - 1, self.height, None, self.select_chain_by_layer, self.set_edit_mode, self.update_zyncoders, self.set_redraw_pending)

		self.main_layer = zynthian_gui_mixer_main_layer()
		self.main_mixbus_strip = zynthian_gui_mixer_strip(self.main_canvas, self.width - self.fader_width - 1, 0, self.fader_width - 1, self.height, self.main_layer, self.select_chain_by_layer, self.set_edit_mode, self.update_zyncoders, self.set_redraw_pending)

		# Edit widgets
		font=(zynthian_gui_config.font_family, int(self.edit_height / 4))
		f=tkFont.Font(family=zynthian_gui_config.font_family, size=int(self.edit_height / 4))
		button_width = f.measure(" BALANCE ") # Width of widest text on edit buttons
		balance_control_bg = self.main_canvas.create_rectangle(self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill=zynthian_gui_config.color_bg, width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_left = self.main_canvas.create_rectangle(int(self.balance_control_centre - self.balance_control_width), 0, self.balance_control_centre, self.balance_control_height, fill="dark red", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.balance_control_right = self.main_canvas.create_rectangle(self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height, fill="dark green", width=0, state="hidden", tags=("edit_control","balance_control"))
		self.main_canvas.tag_bind("balance_control", "<ButtonPress-1>", self.on_balance_press)
		self.main_canvas.tag_bind("balance_control", "<ButtonRelease-1>", self.on_balance_release)
		self.main_canvas.tag_bind("balance_control", "<B1-Motion>", self.on_balance_motion)

		edit_button_x = 1 + int(self.fader_width)
		edit_button_y = self.balance_control_height + 1
		# Solo button
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_strip.solo_color, tags=("edit_control", "solo_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="SOLO", state="hidden", tags=("edit_control", "solo_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_strip.mute_color, tags=("edit_control", "mono_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MONO", state="hidden", tags=("edit_control", "mono_button"), font=font, justify='center')
		# Mute button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_mixer_strip.mute_color, tags=("edit_control", "mute_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="MUTE", state="hidden", tags=("edit_control", "mute_button"), font=font, justify='center')
		# Layer button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark orange", tags=("edit_control", "layer_button"))
		self.layer_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="LAYER", state="hidden", tags=("edit_control", "layer_button"), font=font, justify='center')
		# Reset gain button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_gain_button"))
		self.reset_gain_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nGAIN", state="hidden", tags=("edit_control", "reset_gain_button"), font=font, justify='center')
		# Reset balance button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill="dark blue", tags=("edit_control", "reset_balance_button"))
		self.reset_balance_button_text = self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="RESET\nBALANCE", state="hidden", tags=("edit_control", "reset_balance_button"), font=font, justify='center')
		# Cancel button
		edit_button_y += self.edit_height
		self.main_canvas.create_rectangle(edit_button_x, edit_button_y, edit_button_x + button_width, edit_button_y + self.edit_height, state="hidden", fill=zynthian_gui_config.color_bg, tags=("edit_control", "cancel_button"))
		self.main_canvas.create_text(edit_button_x + int(button_width / 2), edit_button_y + int(self.edit_height / 2), fill="white", text="CANCEL", state="hidden", tags=("edit_control", "cancel_button"), font=font, justify='center')

		self.main_canvas.tag_bind("mute_button", "<ButtonRelease-1>", self.on_mute_release)
		self.main_canvas.tag_bind("solo_button", "<ButtonRelease-1>", self.on_solo_release)
		self.main_canvas.tag_bind("mono_button", "<ButtonRelease-1>", self.on_mono_release)
		self.main_canvas.tag_bind("layer_button", "<ButtonRelease-1>", self.on_layer_release)
		self.main_canvas.tag_bind("reset_gain_button", "<ButtonRelease-1>", self.on_reset_volume_release)
		self.main_canvas.tag_bind("reset_balance_button", "<ButtonRelease-1>", self.on_reset_balance_release)
		self.main_canvas.tag_bind("cancel_button", "<ButtonPress-1>", self.on_cancel_press)

		# Horizontal scroll (via mouse wheel) area
		#legend_height = self.visible_mixer_strips[0].legend_height 
		self.horiz_scroll_bg = self.main_canvas.create_rectangle(0, self.height - 1, self.width, self.height, width=0)
		if os.environ.get("ZYNTHIAN_UI_ENABLE_CURSOR") == "1":
			self.main_canvas.tag_bind(self.horiz_scroll_bg, "<Button-4>", self.on_fader_wheel_up)
			self.main_canvas.tag_bind(self.horiz_scroll_bg, "<Button-5>", self.on_fader_wheel_down)

		zynmixer.enable_dpm(False) # Disable DPM by default - they get enabled when mixer is shown
		if zynthian_gui_config.show_cpu_status:
			self.meter_mode = self.METER_CPU
		else:
			self.meter_mode = self.METER_NONE # Don't show meter in status bar

		# Init touchbar
		self.init_buttonbar()


	# Function to refresh (redraw) balance edit control
	def draw_balance_edit(self):
		balance = zynmixer.get_balance(self.selected_layer.midi_chan)
		if balance > 0:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - (1-balance) * self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width, self.balance_control_height)
		else:
			self.main_canvas.coords(self.balance_control_left, self.balance_control_centre - self.balance_control_width, 0, self.balance_control_centre, self.balance_control_height)
			self.main_canvas.coords(self.balance_control_right, self.balance_control_centre, 0, self.balance_control_centre + self.balance_control_width + self.balance_control_width * balance, self.balance_control_height)


	# Function to force the redrawing of UI controls for all mixer strips
	def draw_mixer_controls(self):
		for strip in range(len(self.visible_mixer_strips)):
			self.visible_mixer_strips[strip].draw_controls()
		self.main_mixbus_strip.draw_controls()


	# Function to redraw, if needed, the UI controls for all mixer strips
	def redraw_mixer_controls(self, force=False):
		for strip in self.visible_mixer_strips:
			strip.redraw_controls(force)
		self.main_mixbus_strip.redraw_controls(force)


	# Function to handle hiding display
	def hide(self):
		zynmixer.enable_dpm(False)
		super().hide()


	# Function to handle showing display
	def show(self):
		if self.shown:
			return
		self.zyngui.screens["control"].unlock_controllers()
		self.set_mixer_mode()
		if self.selected_chain_index == None:
			self.select_chain_by_index(0)
		else:
			self.select_chain_by_index(self.selected_chain_index)
		self.setup_zyncoders()
		zynmixer.enable_dpm(True)
		super().show()


	# Function to refresh loading animation
	def refresh_loading(self):
		pass


	# Function to set flag to refresh all mixer strips
	def set_redraw_pending(self):
		self.redraw_pending = True


	# Function to refresh screen
	def refresh_status(self, status={}):
		if self.shown:
			super().refresh_status(status)
			self.main_mixbus_strip.draw_dpm()
			if self.edit_chain_index is None:
				for strip in range(len(self.visible_mixer_strips)):
					self.visible_mixer_strips[strip].draw_dpm()
			else:
				self.visible_mixer_strips[0].draw_dpm()
				self.draw_balance_edit()
			if self.redraw_pending:
				self.redraw_mixer_controls(True)
				self.redraw_pending = False


	#--------------------------------------------------------------------------
	# Mixer Functionality
	#--------------------------------------------------------------------------

	# Function to get a mixer strip object from a layer index
	# layer_index: Index of layer to get. If None, currently selected layer is used.
	def get_mixer_strip_from_layer_index(self, chi=None):
		if chi is None:
			chi = self.selected_chain_index
		if chi is None or chi < 0:
			return None
		if chi < self.number_layers:
			return self.visible_mixer_strips[chi - self.mixer_strip_offset]
		else:
			return self.main_mixbus_strip


	# Function to highlight the selected mixer strip
	# layer_index: Index of layer to highlight. If None, selected layer is used.
	def highlight_mixer_strip(self, layer_index):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip:
			self.main_canvas.coords(self.selection_highlight, chan_strip.x, chan_strip.height - chan_strip.legend_height, chan_strip.x + chan_strip.width + 1, chan_strip.height)


	# Function to select mixer strip associated with the specified layer
	# layer: Layer object
	# set_curlayer: True to select the layer
	def select_chain_by_layer(self, layer, set_curlayer=True):
		index = 0
		if layer == self.main_layer:
			self.select_chain_by_index(self.number_layers)
			return
		for search_layer in self.zyngui.screens['layer'].root_layers:
			if layer == search_layer:
				self.select_chain_by_index(index, set_curlayer)
				return
			index += 1


	# Function to select chain by index
	#	chain_index: Index of chain to select
	def select_chain_by_index(self, chain_index, set_curlayer=True):
		if self.mode == 0 or chain_index is None or chain_index < 0 or chain_index == self.selected_chain_index or self.number_layers == 0:
			return

		if chain_index > self.number_layers:
			chain_index = self.number_layers
		self.selected_chain_index = chain_index

		if self.selected_chain_index < self.mixer_strip_offset:
			self.mixer_strip_offset = chain_index
			self.set_mixer_mode()
		elif self.selected_chain_index >= self.mixer_strip_offset + len(self.visible_mixer_strips) and self.selected_chain_index != self.number_layers:
			self.mixer_strip_offset = self.selected_chain_index - len(self.visible_mixer_strips) + 1
			self.set_mixer_mode()
		if self.selected_chain_index < self.number_layers:
			self.selected_layer = self.visible_mixer_strips[self.selected_chain_index - self.mixer_strip_offset].layer
		else:
			self.selected_layer = self.main_layer
		self.highlight_mixer_strip(self.selected_chain_index)

		self.update_zyncoders()

		if set_curlayer and self.selected_layer != self.main_layer:
			self.zyngui.set_curlayer(self.selected_layer) #TODO: Lose this re-entrant loop


	# Function to select edit mode
	def set_edit_mode(self, params=None):
		self.mode = 0
		self.edit_chain_index = self.selected_chain_index
		for strip in self.visible_mixer_strips:
			strip.hide()
		strip = len(self.visible_mixer_strips) - 1
		self.main_canvas.itemconfig(self.selection_highlight, state="hidden")
		self.visible_mixer_strips[strip].set_layer(self.selected_layer)
		self.visible_mixer_strips[strip].show()
		self.main_canvas.itemconfig("edit_control", state="normal")
		self.visible_mixer_strips[strip].draw()
		self.draw_balance_edit()
		self.set_title("Edit chain %d" % (self.selected_chain_index + 1))


	# Function change to mixer mode
	def set_mixer_mode(self):
		self.main_canvas.itemconfig("edit_control", state="hidden")
		layers = self.zyngui.screens['layer'].get_root_layers()
		self.number_layers = len(layers)
		for offset in range(len(self.visible_mixer_strips)):
			index = self.mixer_strip_offset + offset
			if index >= self.number_layers:
				self.visible_mixer_strips[offset].set_layer(None)
			else:
				self.visible_mixer_strips[offset].set_layer(layers[index])
		self.main_canvas.itemconfig(self.selection_highlight, state="normal")
		self.mode = 1
		self.edit_chain_index = None
		self.set_title("Audio Mixer")


	# Function to detect if a layer is audio
	#	layer: Layer object
	#	returns: True if audio layer
	def is_audio_layer(self, layer):
		return isinstance(layer, zynthian_gui_mixer_main_layer) or isinstance(layer, zyngine.zynthian_layer) and layer.engine.type != 'MIDI Tool'
		

	# Function to set volume
	#	value: Volume value (0..1)
	#	layer_index: Index of layer to set volume. If None, selected layer is used
	def set_volume(self, value, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip:
			chan_strip.set_volume(value)
			if layer_index == self.selected_chain_index:
				self.update_zyncoders()


	# Function to set volume
	#	value: Balance value (0..1)
	#	layer_index: Index of layer to set volume. If None, selected layer is used
	def set_balance(self, value, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.set_balance(value)
			if layer_index == self.selected_chain_index:
				self.update_zyncoders()


	# Function to reset volume
	#	layer_index: Index of layer to reset volume. If None, selected layer is used
	def reset_volume(self, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.reset_volume()
			if layer_index == self.selected_chain_index:
				self.update_zyncoders()


	# Function to reset balance
	#	layer_index: Index of layer to reset volume. If None, selected layer is used
	def reset_balance(self, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.reset_balance()
			if layer_index == self.selected_chain_index:
				self.update_zyncoders()


	# Function to set mute
	#	value: Mute value (True/False)
	#	layer_index: Index of layer to toggle mute. If None, selected layer is used
	def set_mute(self, value, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.set_mute(value)


	# Function to set solo
	#	value: Solo value (True/False)
	#	layer_index: Index of layer to toggle solo. If None, selected layer is used
	def set_solo(self, value, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.set_solo(value)
			self.main_mixbus_strip.set_redraw_controls()


	# Function to set mono
	#	value: Mono value (True/False)
	#	layer_index: Index of layer to toggle mono. If None, selected layer is used
	def set_mono(self, value, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.set_mono(value)


	# Function to toggle mute
	#	layer_index: Index of layer to toggle mute. If None, selected layer is used
	def toggle_mute(self, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.toggle_mute()


	# Function to toggle solo
	#	layer_index: Index of layer to toggle solo. If None, selected layer is used
	def toggle_solo(self, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip and self.is_audio_layer(chan_strip.layer):
			chan_strip.toggle_solo()
			if chan_strip == self.main_mixbus_strip:
				for strip in self.visible_mixer_strips:
					strip.set_redraw_controls()
			self.main_mixbus_strip.set_redraw_controls()


	# Function to toggle mono
	#	layer_index: Index of layer to toggle mono. If None, selected layer is used
	def toggle_mono(self, layer_index=None):
		chan_strip = self.get_mixer_strip_from_layer_index(layer_index)
		if chan_strip:
			chan_strip.toggle_mono()


	#--------------------------------------------------------------------------
	# Physical UI Control Management: Pots & switches
	#--------------------------------------------------------------------------


	# Function to handle switches press
	#	swi: Switch index [0=Layer, 1=Back, 2=Snapshot, 3=Select]
	#	t: Press type ["S"=Short, "B"=Bold, "L"=Long]
	#	returns True if action fully handled or False if parent action should be triggered
	def switch(self, swi, t):
		if swi == ENC_LAYER:
			if t == "S":
				self.toggle_mute()
				self.redraw_mixer_controls()
				return True

		elif swi == ENC_BACK:
			if t == "S":
				if self.mode == 0:
					self.set_mixer_mode()
					return True
				else:
					self.reset_balance()
					self.redraw_mixer_controls()
					return True

		elif swi == ENC_SNAPSHOT:
			if t == "S":
				self.toggle_solo()
				self.redraw_mixer_controls()
				return True
			elif t == "B":
				# Implement MIDI learning!
				self.zyngui.show_modal('snapshot')
				return True

		elif swi == ENC_SELECT:
			if t == "S":
				if isinstance(self.selected_layer, zyngine.zynthian_layer):
					self.zyngui.layer_control(self.selected_layer)
				return True
			elif t == "B":
				if self.selected_chain_index < self.number_layers:
					# Layer Options
					self.zyngui.screens['layer'].select(self.selected_chain_index)
					self.zyngui.screens['layer_options'].reset()
					self.zyngui.show_modal('layer_options')
				return True

		return False


	def setup_zyncoders(self):
		if not self.selected_layer:
			return
		value = int(zynmixer.get_level(self.selected_layer.midi_chan) * 100)
		lib_zyncore.setup_rangescale_zynpot(ENC_LAYER, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_LAYER, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_LAYER, None)

		value = 50 + int(zynmixer.get_balance(self.selected_layer.midi_chan) * 50)
		lib_zyncore.setup_rangescale_zynpot(ENC_BACK, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_BACK, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_BACK, None)

		value = int(zynmixer.get_level(self.main_layer.midi_chan) * 100)
		lib_zyncore.setup_rangescale_zynpot(ENC_SNAPSHOT, 0, 100, value, 0)
		lib_zyncore.setup_midi_zynpot(ENC_SNAPSHOT, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_SNAPSHOT, None)

		lib_zyncore.setup_rangescale_zynpot(ENC_SELECT, 0, 4 * self.number_layers, 4 * self.selected_chain_index, 1)
		lib_zyncore.setup_midi_zynpot(ENC_SELECT, 0, 0)
		lib_zyncore.setup_osc_zynpot(ENC_SELECT, None)


	# Update the zyncoders values
	def update_zyncoders(self):
		# Selected mixer strip volume & balance
		if self.selected_layer:
			value = int(zynmixer.get_level(self.selected_layer.midi_chan) * 100)
			lib_zyncore.set_value_noflag_zynpot(ENC_LAYER, value, 0)
			value = 50 + int(zynmixer.get_balance(self.selected_layer.midi_chan) * 50)
			lib_zyncore.set_value_noflag_zynpot(ENC_BACK, value, 0)

			# Main mixbus volume
			value = int(zynmixer.get_level(self.main_layer.midi_chan) * 100)
			lib_zyncore.set_value_noflag_zynpot(ENC_SNAPSHOT, value, 0)

		# Selector encoder
		lib_zyncore.set_value_noflag_zynpot(ENC_SELECT, 4 * self.selected_chain_index, 0)


	# Function to handle zyncoder polling.
	def zyncoder_read(self):
		if not self.shown:
			return

		redraw_fader_offset = None
		redraw_main_fader = False

		if self.selected_layer:
			# LAYER encoder adjusts selected chain's level
			if lib_zyncore.get_value_flag_zynpot(ENC_LAYER):
				value = lib_zyncore.get_value_zynpot(ENC_LAYER)
				#logging.debug("Value LAYER: {}".format(value))
				if self.selected_layer == self.main_layer:
					lib_zyncore.set_value_noflag_zynpot(ENC_SNAPSHOT, value)
				zynmixer.set_level(self.selected_layer.midi_chan, value * 0.01)
				if self.selected_layer == self.main_layer:
					redraw_main_fader = True
				else:
					redraw_fader_offset = self.selected_chain_index - self.mixer_strip_offset

			# BACK encoder adjusts selected chain's balance/pan
			if lib_zyncore.get_value_flag_zynpot(ENC_BACK):
				value = lib_zyncore.get_value_zynpot(ENC_BACK)
				#logging.debug("Value BACK: {}".format(value))
				zynmixer.set_balance(self.selected_layer.midi_chan, (value - 50) * 0.02)
				if self.selected_layer == self.main_layer:
					redraw_main_fader = True
				else:
					redraw_fader_offset = self.selected_chain_index - self.mixer_strip_offset

			# SNAPSHOT encoder adjusts main mixbus level
			if lib_zyncore.get_value_flag_zynpot(ENC_SNAPSHOT):
				value = lib_zyncore.get_value_zynpot(ENC_SNAPSHOT)
				#logging.debug("Value SHOT: {}".format(value))
				if self.selected_layer == self.main_layer:
					lib_zyncore.set_value_noflag_zynpot(ENC_LAYER, value)
				zynmixer.set_level(self.main_layer.midi_chan, value * 0.01)
				redraw_main_fader = True

		# SELECT encoder moves chain selection
		if lib_zyncore.get_value_flag_zynpot(ENC_SELECT):
			value = int((1+lib_zyncore.get_value_zynpot(ENC_SELECT))/4)
			#logging.debug("Value SELECT: {}".format(value))
			if (self.mode and value != self.selected_chain_index):
				self.select_chain_by_index(value)

		if redraw_main_fader:
			self.main_mixbus_strip.draw_controls()
		if redraw_fader_offset != None:
			self.visible_mixer_strips[redraw_fader_offset].draw_controls()


	# Increment by inc the zyncoder's value
	def zyncoder_up(self, num, inc = 1):
		lib_zyncore.set_value_zynpot(num, lib_zyncore.get_value_zynpot(num) + inc, 0)


	# Decrement by dec the zyncoder's value
	def zyncoder_down(self, num, dec = 1):
		value = lib_zyncore.get_value_zynpot(num) - dec
		if value < 0:
			value = 0 #TODO: This should be handled by zyncoder
		lib_zyncore.set_value_zynpot(num, value, 0)


	# Function to handle CUIA NEXT command
	def next(self):
		self.select_chain_by_index(self.selected_chain_index+1)


	# Function to handle CUIA PREV command
	def prev(self):
		self.select_chain_by_index(self.selected_chain_index-1)


	# Function to handle CUIA SELECT_UP command
	def select_up(self):
		self.select_chain_by_index(self.selected_chain_index+1)


	# Function to handle CUIA SELECT_DOWN command
	def select_down(self):
		self.select_chain_by_index(self.selected_chain_index-1)


	# Function to handle CUIA BACK_UP command
	def back_up(self):
		self.zyncoder_up(ENC_BACK)


	# Function to handle CUIA BACK_DOWN command
	def back_down(self):
		self.zyncoder_back(ENC_BACK)


	# Function to handle CUIA LAYER_UP command
	def layer_up(self):
		self.zyncoder_up(ENC_LAYER)


	# Function to handle CUIA LAYER_DOWN command
	def layer_down(self):
		self.zyncoder_down(ENC_LAYER)


	# Function to handle CUIA SNAPSHOT_UP command
	def snapshot_up(self):
		self.zyncoder_up(ENC_SNAPSHOT)


	# Function to handle CUIA SNAPSHOT_DOWN command
	def snapshot_down(self):
		self.zyncoder_down(ENC_SNAPSHOT)


	#--------------------------------------------------------------------------
	# OSC message handling
	#--------------------------------------------------------------------------


	# Function to handle OSC messages
	def osc(self, path, args, types, src):
#		print("zynthian_gui_mixer::osc", path, args, types)
		if path[:6] == "VOLUME" or path[:5] == "FADER":
			try:
				self.set_volume(args[0], int(path[5:]))
			except:
				pass
		elif path[:7] == "BALANCE":
			try:
				self.set_balance(args[0], int(path[7:]))
			except:
				pass
		elif path[:4] == "MUTE":
			try:
				self.set_mute(int(args[0]), int(path[4:]))
			except:
				pass
		elif path[:4] == "SOLO":
			try:
				self.set_solo(int(args[0]), int(path[4:]))
			except:
				pass
		self.redraw_mixer_controls()


	#--------------------------------------------------------------------------
	# State Management (mainly used by snapshots)
	#--------------------------------------------------------------------------

	# Get full mixer state
	# Returns: List of mixer strips containing dictionary of each state value
	def get_state(self):
		state = []
		for strip in range(MAX_NUM_CHANNELS + 1):
			state.append({
				'level':zynmixer.get_level(strip),
				'balance':zynmixer.get_balance(strip),
				'mute':zynmixer.get_mute(strip),
				'solo':zynmixer.get_solo(strip),
				'mono':zynmixer.get_mono(strip)
				})
		return state


	# Set full mixer state
	# state: List of mixer stripss containing dictionary of each state value
	def set_state(self, state):
		for strip in range(MAX_NUM_CHANNELS + 1):
			zynmixer.set_level(strip, state[strip]['level'])
			zynmixer.set_balance(strip, state[strip]['balance'])
			zynmixer.set_mute(strip, state[strip]['mute'])
			if strip != MAX_NUM_CHANNELS:
				zynmixer.set_solo(strip, state[strip]['solo'])
			zynmixer.set_mono(strip, state[strip]['mono'])
		self.draw_mixer_controls()


	# Reset mixer to default state
	def reset_state(self):
		for strip in range(MAX_NUM_CHANNELS + 1):
			zynmixer.set_level(strip, 0.8)
			zynmixer.set_balance(strip, 0)
			zynmixer.set_mute(strip, 0)
			zynmixer.set_solo(strip, 0)
			zynmixer.set_mono(strip, 0)
		self.draw_mixer_controls()


	#--------------------------------------------------------------------------
	# GUI Event Management
	#--------------------------------------------------------------------------

	# Function to handle balance press
	#	event: Mouse event
	def on_balance_press(self, event):
		self.balance_drag_start = event


	# Function to handle balance release
	#	event: Mouse event
	def on_balance_release(self, event):
		pass


	# Function to balance fader drag
	#	event: Mouse event
	def on_balance_motion(self, event):
		balance = zynmixer.get_balance(self.selected_layer.midi_chan) + (event.x - self.balance_drag_start.x) / self.balance_control_width
		if balance > 1: balance = 1
		if balance < -1: balance = -1
		self.balance_drag_start = event
		zynmixer.set_balance(self.selected_layer.midi_chan, balance)
		self.draw_balance_edit()


	# Function to handle mute button release
	#	event: Mouse event
	def on_mute_release(self, event):
		self.toggle_mute()
		self.redraw_mixer_controls()


	# Function to handle solo button release
	#	event: Mouse event
	def on_solo_release(self, event):
		self.toggle_solo()
		self.redraw_mixer_controls()


	# Function to handle mono button release
	#	event: Mouse event
	def on_mono_release(self, event):
		self.toggle_mono()
		self.redraw_mixer_controls()


	# Function to handle layer button release
	#	event: Mouse event
	def on_layer_release(self, event):
		self.zyngui.layer_control(self.selected_layer)


	# Function to handle reset volume button release
	#	event: Mouse event
	def on_reset_volume_release(self, event):
		self.reset_volume()
		self.redraw_mixer_controls()


	# Function to handle reset balance button release
	#	event: Mouse event
	def on_reset_balance_release(self, event):
		self.reset_balance()
		self.redraw_controls()


	# Function to handle cancel edit button release
	#	event: Mouse event
	def on_cancel_press(self, event):
		self.set_mixer_mode()


	# Function to handle mouse wheel down when not over fader
	#	event: Mouse event
	def on_fader_wheel_down(self, event):
		if self.mixer_strip_offset < 1:
			return 'break'
		self.mixer_strip_offset -= 1
		self.set_mixer_mode()
		return 'break'


	# Function to handle mouse wheel up when not over fader
	#	event: Mouse event
	def on_fader_wheel_up(self, event):
		if self.mixer_strip_offset +  len(self.visible_mixer_strips) >= self.number_layers:
			return "break"
		self.mixer_strip_offset += 1
		self.set_mixer_mode()
		return 'break'

