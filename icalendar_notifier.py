#!/usr/bin/env python
# -*- coding: utf-8 -*-

#	##### BEGIN GPL LICENSE BLOCK #####
#
#	This program is free software; you can redistribute it and/or
#	modify it under the terms of the GNU General Public License
#	as published by the Free Software Foundation; either version 2
#	of the License, or (at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program; if not, write to the Free Software Foundation,
#	Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
#	##### END GPL LICENSE BLOCK #####

#	Name :
#				iCalendar Notifier
#	Author :
#				▄▄▄▄▄▄▄  ▄ ▄▄ ▄▄▄▄▄▄▄
#				█ ▄▄▄ █ ██ ▀▄ █ ▄▄▄ █
#				█ ███ █ ▄▀ ▀▄ █ ███ █
#				█▄▄▄▄▄█ █ ▄▀█ █▄▄▄▄▄█
#				▄▄ ▄  ▄▄▀██▀▀ ▄▄▄ ▄▄
#				 ▀█▄█▄▄▄█▀▀ ▄▄▀█ █▄▀█
#				 █ █▀▄▄▄▀██▀▄ █▄▄█ ▀█
#				▄▄▄▄▄▄▄ █▄█▀ ▄ ██ ▄█
#				█ ▄▄▄ █  █▀█▀ ▄▀▀  ▄▀
#				█ ███ █ ▀▄  ▄▀▀▄▄▀█▀█
#				█▄▄▄▄▄█ ███▀▄▀ ▀██ ▄

# DEPENDENCIES

from email.mime.text import MIMEText  # MIME types
from email.header import Header  # E-mail header
import configparser  # INI config files parser
import argparse  # "-c" command line argument
import datetime  # Current date + timedelta
import hashlib  # Generate MD5 for strings
import smtplib  # Send e-mails using SMTP
import tkinter  # Pop-up notifications
import urllib.request  # Open URLs
import urllib.parse  # Urlencode
import logging  # Logging
from logging.handlers import RotatingFileHandler
import time
import sys
import os

if (os.name == 'nt'):  # If Microsoft Windows
	import winsound  # Sound notifications

# CONFIGURATION

PROGRAM_NAME = "iCalendar Notifier"
PROGRAM_VERSION = "1.0"

# Command-line interface
argParser = argparse.ArgumentParser(description=PROGRAM_NAME + " " + PROGRAM_VERSION)
# "-c" or "--config" argument
argParser.add_argument('-c', '--config', metavar='PATH', help='"config.ini" configuration file path', required=True)
args = vars(argParser.parse_args())
# INI configuration file path
sConfigFilePath = args['config']

if not os.path.isfile(sConfigFilePath):
	print("Invalid INI configuration file path")
	sys.exit(1)
try:
	configObj = configparser.RawConfigParser()
	configObj.read(sConfigFilePath)
except:
	print("Badly written INI configuration file")
	sys.exit(1)

# LOGGING

# Default logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
if (configObj.getboolean('Logging', 'logging')):
	# Default formatter
	formatter = logging.Formatter('%(asctime)s :: %(levelname)s :: %(message)s')
	# Log maximum 1 Mo to file
	file_handler = RotatingFileHandler(configObj.get('Logging', 'log_file'), 'a', configObj.getint('Logging', 'log_size_in_octets'), 1)
	file_handler.setLevel(logging.DEBUG)
	file_handler.setFormatter(formatter)
	logger.addHandler(file_handler)
	# Log to console
	stream_handler = logging.StreamHandler()
	stream_handler.setLevel(logging.DEBUG)
	logger.addHandler(stream_handler)
logger.info("BEGIN" + ";" + PROGRAM_NAME + ";" + PROGRAM_VERSION)

# ICALENDAR IMPORT : https://github.com/collective/icalendar

try:
	from icalendar import Calendar
except ImportError:
	# Import built-in icalendar python package if not installed
	sys.path.append(configObj.get('Directories', 'modules_directory'))
	from icalendar import Calendar
	logger.warning("icalendar module not found. Using built-in version")

# MAIN PROGRAM

# User-defined webcal URLs, .ics folders and files paths, comma-separated
sCalendarsPaths = configObj.get('Directories', 'urls_and_paths_to_check').split(",")
# Webcal URLs or calendar files paths array
arrCalendars = []
for sCalendarPath in sCalendarsPaths:
	if os.path.isdir(sCalendarPath):
		# Get .ics files paths from user-defined folder
		for sCalendarFileName in os.listdir(sCalendarPath):
			if sCalendarFileName.lower().endswith(".ics"):
				arrCalendars.append(os.path.join(sCalendarPath, sCalendarFileName))
	else:
		arrCalendars.append(sCalendarPath)

# Today's notifiers
dicCalendars = {}
# Notification content
sNotifContent = ""
# Cache folder for webcal calendars
sCachePath = configObj.get('Directories', 'cache_directory')
if not os.path.exists(sCachePath):
	os.makedirs(sCachePath)

iRetryAttemptsIfFailure = configObj.getint('General', 'retry_attempts_if_failure')
iTimeBeforeRetryInSecond = configObj.getint('General', 'time_before_retry_in_seconds')

# For each URL or calendar file path
for sCalendarFilePath in arrCalendars:

	# If webcal URL, download .ics file to .tmp file
	if not os.path.isfile(sCalendarFilePath):
		if sCalendarFilePath[:6] == "webcal":
			logger.info("Webcal : " + sCalendarFilePath)
			sCalendarFilePath = "https" + sCalendarFilePath[6:]
		else:
			logger.warning("Unknown : " + sCalendarFilePath)
		sTmpFilePath = os.path.join(sCachePath, hashlib.md5(sCalendarFilePath.encode('utf-8')).hexdigest() + ".tmp")
		i = 0
		# Retries if fails
		while i <= iRetryAttemptsIfFailure:
			try:
				urllib.request.urlretrieve(sCalendarFilePath, sTmpFilePath)
			except Exception as ex:
				i = i + 1
				logger.warning(str(ex))
				if i > iRetryAttemptsIfFailure:
					# Use old cached version of calendar
					if not os.path.isfile(sTmpFilePath):
						logger.error("Can't retrieve URL, no cached version available")
					else:
						logger.info("Can't retrieve URL, cached version will be used")
						sCalendarFilePath = sTmpFilePath
				else:
					time.sleep(iTimeBeforeRetryInSecond)
			else:
				sCalendarFilePath = sTmpFilePath
				break
	# If file is not a .ics file, let's ignore it
	elif not sCalendarFilePath.lower().endswith(".ics"):
		logger.warning("Ignored file : " + sCalendarFilePath)
		continue
	else:
		logger.info("ICS : " + sCalendarFilePath)

	# Calendar file content
	try:
		fileCalendar = open(sCalendarFilePath, 'rb')
	except:
		continue
	# Calendar object
	calendarObj = Calendar.from_ical(fileCalendar.read())

	# Calendar name
	try:
		sCalendarName = calendarObj['X-WR-CALNAME']
	except KeyError:
		logger.info("No calendar name attribute found")
		sCalendarName = os.path.basename(sCalendarFilePath)

	# Today's date
	dateToday = datetime.date.today()
	if (configObj.getboolean('General', 'get_notified_in_advance')):
		# Today's date + delta
		dateTodayDelta = datetime.date.today() + datetime.timedelta(days=configObj.getint('General', 'days_before_notification'))
	else:
		dateTodayDelta = dateToday

	# For each event from calendar
	for eventObj in calendarObj.walk('VEVENT'):
		# Event start date
		try:
			dateStart = eventObj['DTSTART'].dt
		except:
			logger.info("No start date attribute found on event")
			continue
		# Event end date
		try:
			dateEnd = eventObj['DTEND'].dt
		except:
			dateEnd = dateStart + datetime.timedelta(days=1)
		# Event description
		sEventDescription = eventObj.decoded('summary').decode('utf-8')

		# If event is for today, or between today and today + chosen delta
		if (
				(dateStart.month, dateStart.day) <= (dateToday.month, dateToday.day) < (dateEnd.month, dateEnd.day) or
				(dateToday.month, dateToday.day) <= (dateStart.month, dateStart.day) <= (dateTodayDelta.month, dateTodayDelta.day)):

			# Generate SMS / e-mail / pop-up notification content
			if not sNotifContent:
				dicCalendars[sCalendarFilePath] = sCalendarName
				sNotifContent = sCalendarName + " : " + "\n" + "- " + dateStart.strftime('%d/%m') + " : " + eventObj.decoded('summary').decode('utf-8')
			else:
				if sCalendarFilePath not in dicCalendars:
					dicCalendars[sCalendarFilePath] = sCalendarName
					sNotifContent = sNotifContent + "\n" + sCalendarName + " : " + "\n" + "- " + dateStart.strftime('%d/%m') + " : " + sEventDescription
				else:
					sNotifContent = sNotifContent + "\n" + "- " + dateStart.strftime('%d/%m') + " : " + sEventDescription

	fileCalendar.close()

# NOTIFICATIONS

if dicCalendars:

	# SMS notification

	if (configObj.getboolean('SMS_Notifications', 'sms_notifications')):
		i = 0
		# Retries if fails
		while i <= iRetryAttemptsIfFailure:
			try:
				urllib.request.urlopen("https://smsapi.free-mobile.fr/sendmsg?user=" + configObj.get('SMS_Notifications', 'free_mobile_user') + "&pass=e" + configObj.get('SMS_Notifications', 'free_mobile_password') + "&msg=" + urllib.parse.quote_plus(sNotifContent))
			except Exception as ex:
				i = i + 1
				logger.warning(str(ex))
				if i > iRetryAttemptsIfFailure:
					logger.error("SMS notification not sent")
				else:
					time.sleep(iTimeBeforeRetryInSecond)
				continue
			else:
				logger.info("SMS notification sent")
				break

	# E-mail notification

	if (configObj.getboolean('Email_Notifications', 'email_notifications')):
		# E-mail content
		msg = MIMEText(sNotifContent, 'plain', 'utf-8')
		# E-mail subject, sender, recipient
		msg['Subject'] = Header(configObj.get('Email_Notifications', 'email_subject'), 'utf-8')
		msg['From'] = configObj.get('Email_Notifications', 'email_sender')
		sRecipients = configObj.get('Email_Notifications', 'email_recipients').replace(" ", "").split(",")
		msg['To'] = ", ".join(sRecipients)
		# Send
		i = 0
		# Retries if fails
		while i <= iRetryAttemptsIfFailure:
			try:
				smtp = smtplib.SMTP(configObj.get('Email_Notifications', 'smtp_server'))
				smtp.sendmail(msg['From'], sRecipients, msg.as_string())
			except Exception as ex:
				i = i + 1
				logger.warning(str(ex))
				if i > iRetryAttemptsIfFailure:
					logger.error("E-mail notification not sent")
				else:
					time.sleep(iTimeBeforeRetryInSecond)
				continue
			else:
				logger.info("E-mail notification sent")
				break
		smtp.quit()

	# Sound notification

	if (configObj.getboolean('Sound_Notifications', 'sound_notifications')):
		if (os.name == 'nt'):  # If Microsoft Windows
			winsound.PlaySound(configObj.get('Sound_Notifications', 'sound_file'), winsound.SND_FILENAME|winsound.SND_ASYNC)

	# Pop-up notification

	if (configObj.getboolean('MessageBox_Notifications', 'messagebox_notifications')):
		# Main windows
		root = tkinter.Tk()
		root.resizable(False, False)
		# Invoke buttons on the return key
		root.bind_class('Button', '<Key-Return>', lambda event: event.widget.invoke())
		# Remove the default behavior of invoking the button with the space key
		root.unbind_class('Button', '<Key-space>')
		# Windows icon
		img = tkinter.PhotoImage(file=configObj.get('MessageBox_Notifications', 'icon_file'))
		root.tk.call('wm', 'iconphoto', root._w, img)
		# Topmost Windows ?
		root.attributes('-topmost', configObj.getboolean('MessageBox_Notifications', 'jump_to_the_front'))
		# Windows title
		root.title(PROGRAM_NAME)
		# Windows content
		label = tkinter.Label(root, text=sNotifContent)
		label.config(justify='left')
		#label.grid(row=0, column=0, padx=10, pady=(10, 0), sticky='ew')
		label.pack(fill='both', expand=True, padx=10, pady=(10, 0))
		# "OK" button to close
		button = tkinter.Button(root, text='OK', command=lambda: root.destroy())
		#button.grid(row=1, column=0, padx=10, pady=(10, 10), sticky='ew')
		button.pack(fill='x', expand=True, padx=10, pady=(10, 10))
		button.focus_set()
		# Center main Windows on the screen :
		# Common hack to get the window size : Temporarily hide the window to avoid update_idletasks() drawing the window in the wrong position.
		root.withdraw()
		# Update "requested size" from geometry manager
		root.update_idletasks()
		x = (root.winfo_screenwidth() - root.winfo_reqwidth()) / 2
		y = (root.winfo_screenheight() - root.winfo_reqheight()) / 2
		root.geometry('+%d+%d' % (x, y))
		# Draw the window frame immediately, so only call deiconify() after setting correct window position
		root.deiconify()
		root.mainloop()

logger.info("END" + ";" + PROGRAM_NAME + ";" + PROGRAM_VERSION)
