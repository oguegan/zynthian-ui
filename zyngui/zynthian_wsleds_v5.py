#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian WSLeds Class for V5
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
class zynthian_wsleds_v5(zynthian_wsleds_base):
	
	def __init__(self, zyngui):
		super().__init__(zyngui)
		# LEDS with SPI0 (pin 10, channel 0)
		self.dma = 10
		self.pin = 10
		self.chan = 0
		self.num_leds = 20


	def update_wsleds(self):
		curscreen = self.zyngui.current_screen
		curscreen_obj = self.zyngui.get_current_screen_obj()

		# Menu / Admin
		if self.zyngui.is_current_screen_menu():
			self.setPixelColor(0, self.wscolor_active)
		elif curscreen == "admin":
			self.setPixelColor(0, self.wscolor_active2)
		else:
			self.setPixelColor(0, self.wscolor_default)

		# Audio Mixer / ALSA Mixer
		if curscreen == "audio_mixer":
			self.setPixelColor(1, self.wscolor_active)
		elif curscreen == "alsa_mixer":
			self.setPixelColor(1, self.wscolor_active2)
		else:
			self.setPixelColor(1, self.wscolor_default)

		# Control / Preset Screen:
		if curscreen in ("control", "audio_player"):
			self.setPixelColor(2, self.wscolor_active)
		elif curscreen in ("preset", "bank"):
			self.setPixelColor(2, self.wscolor_active2)
		else:
			self.setPixelColor(2, self.wscolor_default)

		# ZS3 / Snapshot:
		if curscreen == "zs3":
			self.setPixelColor(3, self.wscolor_active)
		elif curscreen == "snapshot":
			self.setPixelColor(3, self.wscolor_active2)
		else:
			self.setPixelColor(3, self.wscolor_default)

		# Zynseq: Zynpad /Pattern Editor
		if curscreen == "zynpad":
			self.setPixelColor(5, self.wscolor_active)
		elif curscreen == "pattern_editor":
			self.setPixelColor(5, self.wscolor_active2)
		else:
			self.setPixelColor(5, self.wscolor_default)

		# Tempo Screen
		if curscreen == "tempo":
			self.setPixelColor(6, self.wscolor_active)
		elif self.zyngui.zynseq.libseq.isMetronomeEnabled():
			self.blink(6, self.wscolor_active)
		else:
			self.setPixelColor(6, self.wscolor_default)

		# ALT button:
		if self.zyngui.alt_mode:
			self.setPixelColor(7, self.wscolor_alt)
		else:
			self.setPixelColor(7, self.wscolor_default)

		wsleds = [8, 9, 10]
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

		# Select/Yes button
		self.setPixelColor(13, self.wscolor_green)

		# Back/No button
		self.setPixelColor(15, self.wscolor_red)

		# Arrow buttons (Up, Left, Bottom, Right)
		self.setPixelColor(14, self.wscolor_yellow)
		self.setPixelColor(16, self.wscolor_yellow)
		self.setPixelColor(17, self.wscolor_yellow)
		self.setPixelColor(18, self.wscolor_yellow)

		# F1-F4 buttons
		if self.zyngui.alt_mode:
			wscolor_fx = self.wscolor_alt
		else:
			wscolor_fx = self.wscolor_default
		self.setPixelColor(4, wscolor_fx)
		self.setPixelColor(11, wscolor_fx)
		self.setPixelColor(12, wscolor_fx)
		self.setPixelColor(19, wscolor_fx)

		try:
			self.zyngui.screens[curscreen].update_wsleds()
		except:
			pass

#------------------------------------------------------------------------------
