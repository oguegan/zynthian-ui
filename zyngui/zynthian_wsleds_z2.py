#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for Z2
#
# Copyright (C) 2015-2023 Fernando Moyano <jofemodo@zynthian.org>
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

# Zynthian specific modules
from zyngui.zynthian_wsleds_base import zynthian_wsleds_base
from zyngui import zynthian_gui_config
from zynlibs.zynseq import zynseq

# ---------------------------------------------------------------------------
# Zynthian WSLeds class for Z2
# ---------------------------------------------------------------------------
class zynthian_wsleds_z2(zynthian_wsleds_base):
	
	def __init__(self, zyngui):
		super().__init__(zyngui)
		if zynthian_gui_config.wiring_layout == "Z2_V1":
			# LEDS with PWM1 (pin 13, channel 1)
			self.dma = 10
			self.pin = 13
			self.chan = 1
			self.num_leds = 25
		elif zynthian_gui_config.wiring_layout in ("Z2_V2", "Z2_V3"):
			# LEDS with SPI0 (pin 10, channel 0)
			self.dma = 10
			self.pin = 10
			self.chan = 0
			self.num_leds = 25


	def update_wsleds(self):
		curscreen = self.zyngui.current_screen
		curscreen_obj = self.zyngui.get_current_screen_obj()

		# Menu
		if self.zyngui.is_current_screen_menu():
			self.setPixelColor(0, self.wscolor_active)
		elif curscreen == "admin":
			self.setPixelColor(0, self.wscolor_active2)
		else:
			self.setPixelColor(0, self.wscolor_default)

		# Active Layer
		if self.zyngui.alt_mode:
			wscolor_light = self.wscolor_alt
			offset = 5
		else:
			wscolor_light = self.wscolor_default
			offset = 0
		# => Light non-empty layers
		n = self.zyngui.screens['layer'].get_num_root_layers()
		main_fxchain = self.zyngui.screens['layer'].get_main_fxchain_root_layer()
		if main_fxchain:
			n -= 1
		for i in range(5):
			if i + offset < n:
				self.setPixelColor(1 + i, wscolor_light)
			else:
				self.setPixelColor(1 + i, self.wscolor_off)
		# => Light FX layer if not empty
		if main_fxchain:
			self.setPixelColor(6, self.wscolor_default)
		else:
			self.setPixelColor(6, self.wscolor_off)
		# => Light active layer
		i = self.zyngui.screens['layer'].get_root_layer_index()
		if i is not None:
			if main_fxchain and i == n:
				if curscreen == "control":
					self.setPixelColor(6, self.wscolor_active)
				else:
					self.blink(6, self.wscolor_active)
			elif i + offset < 5:
				if curscreen == "control":
					self.setPixelColor(1 + i, self.wscolor_active)
				else:
					self.blink(1 + i, self.wscolor_active)

		# MODE button => MIDI LEARN
		if self.zyngui.midi_learn_zctrl or curscreen == "zs3":
			self.setPixelColor(7, self.wscolor_yellow)
		elif self.zyngui.midi_learn_mode:
			self.setPixelColor(7, self.wscolor_active)
		else:
			self.setPixelColor(7, self.wscolor_default)

		# Zynpad screen:
		if curscreen == "zynpad":
			self.setPixelColor(8, self.wscolor_active)
		else:
			self.setPixelColor(8, self.wscolor_default)

		# Pattern Editor/Arranger screen:
		if curscreen == "pattern_editor":
			self.setPixelColor(9, self.wscolor_active)
		elif curscreen == "arranger":
			self.setPixelColor(9, self.wscolor_active2)
		else:
			self.setPixelColor(9, self.wscolor_default)

		# Control / Preset Screen:
		if curscreen in ("control", "audio_player"):
			self.setPixelColor(10, self.wscolor_active)
		elif curscreen in ("preset", "bank"):
			if self.zyngui.curlayer.get_show_fav_presets():
				self.blink(10, self.wscolor_active2)
			else:
				self.setPixelColor(10, self.wscolor_active2)
		else:
			self.setPixelColor(10, self.wscolor_default)

		# ZS3/Snapshot screen:
		if curscreen == "zs3":
			self.setPixelColor(11, self.wscolor_active)
		elif curscreen == "snapshot":
			self.setPixelColor(11, self.wscolor_active2)
		else:
			self.setPixelColor(11, self.wscolor_default)

		# ???:
		self.setPixelColor(12, self.wscolor_default)

		# ALT button:
		if self.zyngui.alt_mode:
			self.setPixelColor(13, self.wscolor_alt)
		else:
			self.setPixelColor(13, self.wscolor_default)

		wsleds = [14, 17, 15]
		update_wsleds_func = getattr(curscreen_obj, "update_wsleds", None)
		if callable(update_wsleds_func):
			update_wsleds_func(wsleds)
		else:
			if self.zyngui.alt_mode:
				self.zyngui.screens["midi_recorder"].update_wsleds(wsleds)
			else:
				# REC Button
				if 'audio_recorder' in self.zyngui.status_info:
					self.setPixelColor(wsleds[0], self.wscolor_red)
				else:
					self.setPixelColor(wsleds[0], self.wscolor_default)
				# STOP button
				self.setPixelColor(wsleds[1], self.wscolor_default)
				# PLAY button:
				if 'audio_player' in self.zyngui.status_info:
					self.setPixelColor(wsleds[2], self.wscolor_green)
				else:
					self.setPixelColor(wsleds[2], self.wscolor_default)

		# Tempo Screen
		if curscreen == "tempo":
			self.setPixelColor(16, self.wscolor_active)
		elif self.zyngui.zynseq.libseq.isMetronomeEnabled():
			self.blink(16, self.wscolor_active)
		else:
			self.setPixelColor(16, self.wscolor_default)

		# Select/Yes button
		self.setPixelColor(20, self.wscolor_green)

		# Back/No button
		self.setPixelColor(18, self.wscolor_red)

		# Arrow buttons (Up, Left, Bottom, Right)
		self.setPixelColor(19, self.wscolor_yellow)
		self.setPixelColor(21, self.wscolor_yellow)
		self.setPixelColor(22, self.wscolor_yellow)
		self.setPixelColor(23, self.wscolor_yellow)

		# Audio Mixer / ALSA Mixer
		if curscreen == "audio_mixer":
			self.setPixelColor(24, self.wscolor_active)
		elif curscreen == "alsa_mixer":
			self.setPixelColor(24, self.wscolor_active2)
		else:
			self.setPixelColor(24, self.wscolor_default)

		try:
			self.zyngui.screens[curscreen].update_wsleds()
		except:
			pass

#------------------------------------------------------------------------------
