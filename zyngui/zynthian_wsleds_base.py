#!/usr/bin/python3
# -*- coding: utf-8 -*-
#******************************************************************************
# ZYNTHIAN PROJECT: Zynthian GUI
#
# Zynthian GUI Base Class for WS281X LEDs Management
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

import logging
from zyncoder.zyncore import lib_zyncore

# Zynthian specific modules
from zyngui import zynthian_gui_config

# ---------------------------------------------------------------------------
# Zynthian GUI Base Class for WS281X LEDs Management
# ---------------------------------------------------------------------------
class zynthian_wsleds_base:
	
	def __init__(self, zyngui):
		self.zyngui = zyngui
		# LED strip variables
		self.dma = None
		self.pin = None
		self.chan = None
		self.wsleds = None
		self.i2cAddr = 0x40
		self.num_leds = 0
		self.blink_count = 0
		self.blink_state = False
		self.pulse_step = 0
		self.last_wsled_state = ""
		self.brightness = 1
		self.setup_colors()


	def setup_colors(self):
		# Predefined colors
		self.wscolor_off = self.create_color(0, 0, 0)
		self.wscolor_white = self.create_color(120, 120, 120)
		self.wscolor_red = self.create_color(140, 0, 0)
		self.wscolor_green = self.create_color(0, 220, 0)
		self.wscolor_yellow = self.create_color(160, 160, 0)
		self.wscolor_orange = self.create_color(190, 80, 0)
		self.wscolor_blue = self.create_color(0, 0, 220)
		self.wscolor_blue_light = self.create_color(0, 130, 130)
		self.wscolor_purple = self.create_color(130, 0, 130)
		self.wscolor_default = self.wscolor_blue
		self.wscolor_alt = self.wscolor_purple
		self.wscolor_active = self.wscolor_green
		self.wscolor_active2 = self.wscolor_orange
		self.wscolor_admin = self.wscolor_red
		self.wscolor_low = self.create_color(0, 100, 0)
		# Color Codes
		self.wscolors_dict = {
			str(self.wscolor_off): "0",
			str(self.wscolor_blue): "B",
			str(self.wscolor_green): "G",
			str(self.wscolor_red): "R",
			str(self.wscolor_orange): "O",
			str(self.wscolor_yellow): "Y",
			str(self.wscolor_purple): "P"
		}
		self.listPixels=[str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off),str(self.wscolor_off)]

	def create_color(self, r, g, b):
		return [int(self.brightness * r), int(self.brightness * g), int(self.brightness * b)]


	def set_brightness(self, brightness):
		if brightness < 0:
			self.brightness = 0
		elif brightness > 1:
			self.brightness = 0
		else:
			self.brightness = brightness
		self.setup_colors()


	def get_brightness(self):
		return self.brightness


	def start(self):
		if self.num_leds > 0 and self.pin is not None:
			self.wsleds = 0
			for i in range(0, self.num_leds):
				self.listPixels.append(str(self.wscolor_off))
			self.light_on_all()


	def end(self):
		self.light_off_all()


	def get_num(self):
		return self.num_leds


	def setPixelColor(self, i , wscolor):
		lib_zyncore.set_led(i, wscolor[0], wscolor[1], wscolor[2])
		self.listPixels[i] = str(wscolor)


	def light_on_all(self):
		if self.num_leds > 0:
			# Light all LEDs
			lib_zyncore.set_all_leds(self.wscolor_default[0], self.wscolor_default[1], self.wscolor_default[2])
			for i in range(0, self.num_leds):
				self.listPixels[i] = str(self.wscolor_default)


	def light_off_all(self):
		if self.num_leds > 0:
			# Light-off all LEDs
			lib_zyncore.reset_all_leds()
			for i in range(0, self.num_leds):
				self.listPixels[i] = str(self.wscolor_off)



	def blink(self, i, color):
		if self.blink_state:
			self.setPixelColor(i, color)
		else:
			self.setPixelColor(i, self.wscolor_off)


	def pulse(self, i):
		if self.blink_state:
			color = self.create_color(0, int(self.brightness * self.pulse_step * 6), 0)
			self.pulse_step += 1
		elif self.pulse_step > 0:
			color = self.create_color(0, int(self.brightness * self.pulse_step * 6), 0)
			self.pulse_step -= 1
		else:
			color = self.wscolor_off
			self.pulse_step = 0

		self.setPixelColor(i, color)

	def update(self):
		# Power Save Mode
		if self.zyngui.power_save_mode:
			if self.blink_count % 64 > 44:
				self.blink_state = True
			else:
				self.blink_state = False
			self.light_off_all
			self.pulse(0)

		# Normal mode
		else:
			if self.blink_count % 4 > 1:
				self.blink_state = True
			else:
				self.blink_state = False

			try:
				self.update_wsleds()
			except Exception as e:
				logging.error(e)


			if self.zyngui.capture_log_fname:
				try:
					wsled_state = []
					for i in range(self.num_leds):
						c = self.listPixels[i]
						if c in self.wscolors_dict:
							wsled_state.append(self.wscolors_dict[c])
					wsled_state = ",".join(wsled_state)
					if wsled_state != self.last_wsled_state:
						self.last_wsled_state = wsled_state
						self.zyngui.write_capture_log("LEDSTATE:" + wsled_state)
				except Exception as e:
					logging.error(e)

		self.blink_count += 1


	def reset_last_state(self):
		self.last_wsled_state = ""


	def update_wsleds(self):
		pass


#------------------------------------------------------------------------------
