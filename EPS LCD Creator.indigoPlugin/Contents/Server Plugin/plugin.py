#! /usr/bin/env python
# -*- coding: utf-8 -*-

import indigo

import os
import sys
import time
import datetime

from eps.cache import cache
from eps.lcd import lcd
from eps import ui
from eps import dtutil

from eps import plug
from eps import eps

from bs4 import BeautifulSoup # 1.12
import urllib2 # 1.12
import re # 1.12
from datetime import timedelta # 1.12

################################################################################
class Plugin(indigo.PluginBase):
	
	#
	# Init
	#
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		# EPS common startup
		try:
			self.debug = pluginPrefs["debugMode"]
			pollingMode = pluginPrefs["pollingMode"]
			pollingInterval = int(pluginPrefs["pollingInterval"])
			pollingFrequency = pluginPrefs["pollingFrequency"]
			self.monitor = pluginPrefs["monitorChanges"]
		except:
			indigo.server.log ("Preference options may have changed or are corrupt,\n\tgo to Plugins -> %s -> Configure to reconfigure %s and then reload the plugin.\n\tUsing defaults for now, the plugin should operate normally." % (pluginDisplayName, pluginDisplayName), isError = True)
			self.debug = False
			pollingMode = "realTime"
			pollingInterval = 1
			pollingFrequency = "s"
			
		# EPS common variables and classes
		self.pluginUrl = "http://forums.indigodomo.com/viewtopic.php?f=198&t=16239" # 1.12 # http://forums.indigodomo.com/viewtopic.php?f=198&t=16239
		self.reload = False
		self.cache = cache (self, pluginId, pollingMode, pollingInterval, pollingFrequency)
		
		# EPS plugin specific variables and classes
		self.lcd = lcd ()
		plug.parent = self
		
			
	################################################################################
	# EPS ROUTINES
	################################################################################
	
	#
	# Plugin menu: Performance options
	#
	def performanceOptions (self, valuesDict, typeId):
		self.debugLog(u"Saving performance options")
		errorsDict = indigo.Dict()
		
		# Save the performance options into plugin prefs
		self.pluginPrefs["pollingMode"] = valuesDict["pollingMode"]
		self.pluginPrefs["pollingInterval"] = valuesDict["pollingInterval"]
		self.pluginPrefs["pollingFrequency"] = valuesDict["pollingFrequency"]
		
		self.cache.setPollingOptions (valuesDict["pollingMode"], valuesDict["pollingInterval"], valuesDict["pollingFrequency"])
		
		return (True, valuesDict, errorsDict)
		
	#
	# Plugin menu: Library versions
	#
	def showLibraryVersions (self, forceDebug = False):
		s =  eps.debugHeader("LIBRARY VERSIONS")
		s += eps.debugLine (self.pluginDisplayName + " - v" + self.pluginVersion)
		s += eps.debugHeaderEx ()
		s += eps.debugLine ("Cache %s" % self.cache.version)
		s += eps.debugLine ("LCD %s" % self.lcd.version)
		s += eps.debugLine ("UI %s" % ui.libVersion(True))
		s += eps.debugLine ("DateTime %s" % dtutil.libVersion(True))
		s += eps.debugLine ("Core %s" % eps.libVersion(True))
		s += eps.debugHeaderEx ()
		
		if forceDebug:
			self.debugLog (s)
			return
			
		indigo.server.log (s)
		
	#
	# Device action: Update
	#
	def updateDevice (self, devAction):
		dev = indigo.devices[devAction.deviceId]
		self.updateDeviceStates (dev)
		
		return
		
	#
	# Update device
	#
	def updateDeviceStates (self, parentDev, childDev = None):
		stateChanges = self.cache.deviceUpdate (parentDev)
		
		children = self.cache.getSubDevices (parentDev)
		for devId in children:
			childDev = indigo.devices[int(devId)]	
			plug.updateChangedLCD (childDev, stateChanges)
		
		return
		
	#
	# Add watched states
	#
	def addWatchedStates (self, subDevId = "*", deviceTypeId = "*", mainDevId = "*"):
		if deviceTypeId == "*" or deviceTypeId == "epslcdsb":
			if mainDevId != "*":
				dev = indigo.devices[int(mainDevId)]
				devChild = indigo.devices[int(dev.pluginProps["device"])]
				subDevId = devChild.id # Must be specific for multiple choice
				
				for i in range (1, 6):
					if eps.propValid (dev, "state" + str(i), True):
						self.cache.addWatchState (dev.pluginProps["state" + str(i)], subDevId, "epslcdsb", dev.id)
		
		elif deviceTypeId == "*" or deviceTypeId == "epslcddt": # 1.12
			dev = indigo.devices[int(mainDevId)]
			if dev.pluginProps["systemdate"] == False and dev.pluginProps["usevariable"] == False:
				if mainDevId != "*":
					devChild = indigo.devices[int(dev.pluginProps["device"])]
					subDevId = devChild.id # Must be specific for multiple choice
					
					if eps.propValid (dev, "state", True):
						if eps.propValid (devChild, dev.pluginProps["state"]):
							self.cache.addWatchState (dev.pluginProps["state"], subDevId, "epslcddt", dev.id)	
						else:
							self.cache.addWatchProperty (dev.pluginProps["state"], subDevId, "epslcddt", dev.id)	
							
							# Since properties don't auto-update, force an update here - the only thing we are doing
							# this on is lastChanged
							self.dateTimeDeviceUpdate (dev, dev.lastChanged)
							
		
		elif deviceTypeId == "*" or deviceTypeId == "epslcdalc":
			for s in plug.defAlarmClock:
				self.cache.addWatchState (s, subDevId, "epslcdalc")
				
			dev = indigo.devices[int(mainDevId)]
					
		elif deviceTypeId == "*" or deviceTypeId == "epslcdth":
			for s in plug.defThermostat:
				self.cache.addWatchState (s, subDevId, "epslcdth")
				
			dev = indigo.devices[int(mainDevId)]
				
			# If an extended device was configure then add watches for it
			if eps.propValid (dev, "device2", True):
				devExtended = indigo.devices[int(dev.pluginProps["device2"])]
				for s in plug.defThermostatEx:
					self.cache.addWatchState (s, devExtended.id, "*", dev.id) 
					
		elif deviceTypeId == "*" or deviceTypeId == "epslcdwe":
			if mainDevId != "*":
				# self, stateName, subDevId = "*", deviceTypeId = "*", mainDevId = "*"
				dev = indigo.devices[int(mainDevId)]
				devChild = indigo.devices[int(dev.pluginProps["device"])]
				subDevId = devChild.id # Must be specific for multiple choice
				
				# If an extended device was configure then add watches for it
				if eps.propValid (dev, "device2", True):
					devExtended = indigo.devices[int(dev.pluginProps["device2"])]
					for s in plug.defWeatherEx:
						self.cache.addWatchState (s, devExtended.id, "*", dev.id) 
				
				if devChild.pluginId == "com.fogbert.indigoplugin.wunderground": # Weather Underground plugin		
					for s in plug.defWUnderground:
						self.cache.addWatchState (s, subDevId, "epslcdwe", dev.id) 
				
				elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop": # Weathersnoop plugin	
					for s in plug.defWeathersnoop:
						self.cache.addWatchState (s, subDevId, "epslcdwe", dev.id)
					
					self.cache.addWatchState ("temperature_" + dev.pluginProps["temps"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("dayRain_" + dev.pluginProps["measures"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("rainOneHour_" + dev.pluginProps["measures"], subDevId, "epslcdwe", dev.id)
					
					# 1.1.0 from dewPoint to Pressure
					self.cache.addWatchState ("dewPoint" + dev.pluginProps["temps"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("windChill" + dev.pluginProps["temps"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("windSpeed_" + dev.pluginProps["speed"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("windGust_" + dev.pluginProps["speed"], subDevId, "epslcdwe", dev.id)
					self.cache.addWatchState ("relativeBarometricPressure_" + dev.pluginProps["pressure"], subDevId, "epslcdwe", dev.id)
					
				
				elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.NOAAWeather": # NOAA
					for s in plug.defNOAA:
						self.cache.addWatchState (s, subDevId, "epslcdwe", dev.id)
				
		elif deviceTypeId == "*" or deviceTypeId == "epslcdir":
			for s in plug.defSprinklers:
				self.cache.addWatchState (s, subDevId, "epslcdir")
				
			dev = indigo.devices[int(mainDevId)]
				
			# If an extended device was configure then add watches for it
			if eps.propValid (dev, "device2", True):
				devExtended = indigo.devices[int(dev.pluginProps["device2"])]
				for s in plug.defIrrigationEx:
					self.cache.addWatchState (s, devExtended.id, "*", dev.id) 
			
		#self.cache.dictDump (self.cache.devices)
		
		return
		
	
	################################################################################
	# EPS HANDLERS
	################################################################################
		
	#
	# Device menu selection changed
	#
	def onDeviceSelectionChange (self, valuesDict, typeId, devId):
		# Just here so we can refresh the states for dynamic UI
		# While building the list of devices, see if there is an EPS Device Extension for this type of device that we can use
		if typeId == "epslcdwe":
			if "foundExtended" in valuesDict:
				for dev in indigo.devices.iter("com.eps.indigoplugin.device-extensions.epsdews"):
					valuesDict["foundExtended"] = True
					
		if typeId == "epslcdth":
			if "foundExtended" in valuesDict:
				for dev in indigo.devices.iter("com.eps.indigoplugin.device-extensions.epsdeth"):
					valuesDict["foundExtended"] = True
					
		if typeId == "epslcdir":
			if "foundExtended" in valuesDict:
				for dev in indigo.devices.iter("com.eps.indigoplugin.device-extensions.epsdeirr"):
					valuesDict["foundExtended"] = True
						
		return valuesDict
		
	#
	# Return option array of device states to (filter is the device to query)
	#
	def getStatesForDevice(self, filter="", valuesDict=None, typeId="", targetId=0):
		return ui.getStatesForDevice (filter, valuesDict, typeId, targetId)
		
	#
	# Special version of device states to also get the lastChanged date on date/time devices - 1.12
	#
	def getStatesForDeviceDateTime(self, filter="", valuesDict=None, typeId="", targetId=0):
		states = ui.getStatesForDevice (filter, valuesDict, typeId, targetId)
		
		option = ("lastChanged", "lastChanged (property)")
		states.append(option)
		
		return states
		
		
	#
	# Return option array of device plugin props to (filter is the device to query)
	#
	def getPropsForDevice(self, filter="", valuesDict=None, typeId="", targetId=0):
		return ui.getPropsForDevice (filter, valuesDict, typeId, targetId)
		
	#
	# Return option array of plugin devices props to (filter is the plugin(s) to query)
	#
	def getPluginDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
		return ui.getPluginDevices (filter, valuesDict, typeId, targetId)
		
	#
	# Handle ui button click
	#
	def uiButtonClicked (self, valuesDict, typeId, devId):
		return valuesDict
		
	#
	# Concurrent thread process fired
	#
	def onRunConcurrentThread (self):
		self.updateCheck(True, False) # 1.12
		self.updateDateTime() # 1.12
		return
		
	
				
		
		
	################################################################################
	# EPS ROUTINES TO BE PUT INTO THEIR OWN CLASSES / METHODS
	################################################################################
	
	#
	# Update date/time device value based on device or variable change
	#
	def dateTimeDeviceUpdate (self, dev, value): 
		try:
			value = unicode(value)
			d = datetime.datetime.strptime (value, dev.pluginProps["valueformat"])
			
			if eps.valueValid (dev.pluginProps, "dateformat", True):
				value = d.strftime(dev.pluginProps["dateformat"])
				value = self.lcd.stringToLCD (value, 20, dev.pluginProps["textspaces"])
				self.lcd.stringToGraphics (dev, "currentDate", value)
				
		except Exception as e:
			eps.printException(e)
	
	
	#
	# Update date and time for any date/time devices that are using the system clock - 1.12
	#
	def updateDateTime (self):
		d = indigo.server.getTime()
		for dev in indigo.devices.iter(self.pluginId + ".epslcddt"):
			if dev.pluginProps["systemdate"] == False: continue # they are watching states / variables
		
			if eps.valueValid(dev.states, "storeddate", True):
				if dev.states["storeddate"] == d.strftime("%Y-%m-%d %H:%M:00"):
					continue # we don't calculate seconds, only update if Y-M-D or H:M updated
			else:
				dev.updateStateOnServer("storeddate", d.strftime("%Y-%m-%d %H:%M:00"))
							
			if eps.valueValid (dev.pluginProps, "dateformat", True):
				value = d.strftime(dev.pluginProps["dateformat"])
				value = self.lcd.stringToLCD (value, 20, dev.pluginProps["textspaces"])
				self.lcd.stringToGraphics (dev, "currentDate", value)
				
			dev.updateStateOnServer("storeddate", d.strftime("%Y-%m-%d %H:%M:00"))
	
	################################################################################
	# INDIGO DEVICE EVENTS
	################################################################################
	
	#
	# Device starts communication
	#
	def deviceStartComm(self, dev):
		self.debugLog(u"%s starting communication" % dev.name)
		dev.stateListOrDisplayStateIdChanged() # Force plugin to refresh states from devices.xml 1.1.0
		
		if self.cache is None: return
		
		if "lastreset" in dev.states:
			d = indigo.server.getTime()
			if dev.states["lastreset"] == "": dev.updateStateOnServer("lastreset", d.strftime("%Y-%m-%d "))
							
		if self.cache.deviceInCache (dev.id) == False:
			self.debugLog(u"%s not in cache, appears to be a new device or plugin was just started" % dev.name)
			self.cache.cacheDevices() # Failsafe
			
		self.addWatchedStates("*", dev.deviceTypeId, dev.id) # Failsafe
		#self.cache.dictDump (self.cache.devices[dev.id])
		self.updateDeviceStates(dev)
		
		dev.updateStateImageOnServer(indigo.kStateImageSel.None)
		dev.updateStateOnServer(key="statedisplay", value=True, uiValue="True")
		
		if dev.deviceTypeId == "epslcdwe":
			try:
				# 1.1.0 added preferences for speed
				if eps.propValid(dev, "speed", True) == False: 
					props = dev.pluginProps
					props["speed"] = "mph"
					dev.replacePluginPropsOnServer(props)
				
				# 1.1.0 added preferences for pressure
				if eps.propValid(dev, "pressure", True) == False: 
					props = dev.pluginProps
					props["pressure"] = "inHg"
					dev.replacePluginPropsOnServer(props)
			except:
				indigo.server.log("Error trying to save new device properties, please edit the device and re-save properties to get past this issue", isError=True)
		
		if dev.deviceTypeId == "epslcdir":
			# Extract zone names
			loop = 1
			if eps.propValid (dev, "device", True):
				devEx = indigo.devices[int(dev.pluginProps["device"])]
				self.debugLog ("\tGetting zone names from %s" % devEx.name)
				for s in devEx.zoneNames:
					#def stringToLCD (self, value, length, padLeft = False):
					value = self.lcd.stringToLCD (s, 20, dev.pluginProps["textspaces"])
					self.debugLog ("\t\t%s returned value is %s" % (s, value))
					self.lcd.stringToGraphics (dev, "zonename" + str(loop) + "_", s)
					
					loop = loop + 1
			
		return
			
	#
	# Device stops communication
	#
	def deviceStopComm(self, dev):
		self.debugLog(u"%s stopping communication" % dev.name)
		
	#
	# Device property changed
	#
	def didDeviceCommPropertyChange(self, origDev, newDev):
		self.debugLog(u"%s property changed" % origDev.name)
		return True	
	
	#
	# Device property changed
	#
	def deviceUpdated(self, origDev, newDev):
		if self.cache is None: return
		
		if newDev.pluginId == self.pluginId:
			#self.debugLog(u"Plugin device %s was updated" % origDev.name)
			
			# Re-cache the device and it's subdevices and states
			if eps.propsChanged (origDev, newDev):
				self.debugLog(u"Plugin device %s settings changed, rebuilding watched states" % origDev.name)
				self.cache.removeDevice (origDev.id)
				self.deviceStartComm (newDev)
						
		else:
			changedStates = self.cache.watchedStateChanged (origDev, newDev)
			if changedStates:
				self.debugLog(u"The monitored device %s had a watched state change" % origDev.name)
				#indigo.server.log(unicode(changedStates))
				plug.updateChangedLCD (newDev, changedStates)
				
			changedStates = self.cache.watchedPropertyChanged (origDev, newDev)
			if changedStates:
				self.debugLog(u"The monitored device %s had a watched property change" % origDev.name)
				
				for devId, devProps in changedStates.iteritems():
					dev = indigo.devices[devId]
					if dev.deviceTypeId == "epslcddt":
						self.dateTimeDeviceUpdate (dev, dev.lastChanged)
				
		return
		
	#
	# Variable updated - 1.12
	#
	def variableUpdated (self, origVariable, newVariable):
		# Since we don't use variable caching find any date/time devices using variables
		for dev in indigo.devices.iter(self.pluginId + ".epslcddt"):
			if dev.pluginProps["usevariable"] and eps.valueValid(dev.pluginProps, "variable", True):
				if str(origVariable.id) == dev.pluginProps["variable"]:
					# Our watched variable changed, update
					self.debugLog(u"The monitored variable %s changed" % newVariable.name)
					self.dateTimeDeviceUpdate (dev, newVariable.value)
		
	#
	# Device deleted
	#
	def deviceDeleted(self, dev):
		if dev.pluginId == self.pluginId:
			self.debugLog("%s was deleted" % dev.name)
			self.cache.removeDevice (dev.id)
		
	
	################################################################################
	# INDIGO DEVICE UI EVENTS
	################################################################################	
	
		
	#
	# Device pre-save event
	#
	def validateDeviceConfigUi(self, valuesDict, typeId, devId):
		dev = indigo.devices[devId]
		self.debugLog(u"%s is validating device configuration UI" % dev.name)
		return (True, valuesDict)
		
	#
	# Device config button clicked event
	#
	def closedDeviceConfigUi(self, valuesDict, userCancelled, typeId, devId):
		dev = indigo.devices[devId]
		self.debugLog(u"%s is closing device configuration UI" % dev.name)
		
		if userCancelled == False: 
			self.debugLog(u"%s configuration UI was not cancelled" % dev.name)
			
		#self.cache.dictDump (self.cache.devices[dev.id])
			
		return
		
	#
	# Event pre-save event
	#
	def validateEventConfigUi(self, valuesDict, typeId, eventId):
		self.debugLog(u"Validating event configuration UI")
		return (True, valuesDict)
		
	#
	# Event config button clicked event
	#
	def closedEventConfigUi(self, valuesDict, userCancelled, typeId, eventId):
		self.debugLog(u"Closing event configuration UI")
		return
		
	#
	# Action pre-save event
	#
	def validateActionConfigUi(self, valuesDict, typeId, actionId):
		self.debugLog(u"Validating event configuration UI")
		return (True, valuesDict)
		
	#
	# Action config button clicked event
	#
	def closedActionConfigUi(self, valuesDict, userCancelled, typeId, actionId):
		self.debugLog(u"Closing action configuration UI")
		return
		
		
	################################################################################
	# INDIGO PLUGIN EVENTS
	################################################################################	
	
	#
	# Plugin startup
	#
	def startup(self):
		self.debugLog(u"Starting plugin")
		if self.cache is None: return
		
		if self.monitor: 
			if self.cache.pollingMode == "realTime": 
				indigo.devices.subscribeToChanges()
				indigo.variables.subscribeToChanges() # 1.12
		
		# Add all sub device variables that our plugin links to, reloading only on the last one
		#self.cache.addSubDeviceVar ("weathersnoop", False) # Add variable, don't reload cache
		#self.cache.addSubDeviceVar ("irrigation") # Add variable, reload cache
		
		# Not adding any sub device variables, reload the cache manually
		self.cache.cacheDevices()
		
		#self.cache.dictDump (self.cache.devices)
		
		return
		
	#	
	# Plugin shutdown
	#
	def shutdown(self):
		self.debugLog(u"Plugin shut down")	
	
	#
	# Concurrent thread
	#
	def runConcurrentThread(self):
		if self.cache is None:
			try:
				while True:
					self.sleep(1)
					if self.reload: break
			except self.StopThread:
				pass
			
			# Only happens if we break out due to a restart command
			serverPlugin = indigo.server.getPlugin(self.pluginId)
			serverPlugin.restart(waitUntilDone=False)
				
			return
		
		try:
			while True:
				if self.cache.pollingMode == "realTime" or self.cache.pollingMode == "pollDevice":
					self.onRunConcurrentThread()
					self.sleep(1)
					if self.reload: break
				else:
					self.onRunConcurrentThread()
					self.sleep(self.cache.pollingInterval)
					if self.reload: break
					
				# Only happens if we break out due to a restart command
				serverPlugin = indigo.server.getPlugin(self.pluginId)
         		serverPlugin.restart(waitUntilDone=False)
		
		except self.StopThread:
			pass	# Optionally catch the StopThread exception and do any needed cleanup.
	
	
	################################################################################
	# INDIGO PLUGIN UI EVENTS
	################################################################################	
	
	#
	# Plugin config pre-save event
	#
	def validatePrefsConfigUi(self, valuesDict):
		self.debugLog(u"%s is validating plugin config UI" % self.pluginDisplayName)
		return (True, valuesDict)
		
	#
	# Plugin config button clicked event
	#
	def closedPrefsConfigUi(self, valuesDict, userCancelled):
		self.debugLog(u"%s is closing plugin config UI" % self.pluginDisplayName)
		
		if userCancelled == False:
			if "debugMode" in valuesDict:
				self.debug = valuesDict["debugMode"]
				
		return
			
	#
	# Stop concurrent thread
	#
	def stopConcurrentThread(self):
		self.debugLog(u"Plugin stopping concurrent threads")	
		self.stopThread = True
		
	#
	# Delete
	#
	def __del__(self):
		self.debugLog(u"Plugin delete")	
		indigo.PluginBase.__del__(self)
		
	
	################################################################################
	# PLUGIN SPECIFIC ROUTINES
	################################################################################	
	
	#
	# State based LCD 1st state clear button clicked
	#
	def uiButtonClicked_State1 (self, valuesDict, typeId, devId):
		valuesDict["state1"] = ""
		valuesDict["type1"] = "auto"
		return valuesDict	
		
	#
	# State based LCD 2nd state clear button clicked
	#
	def uiButtonClicked_State2 (self, valuesDict, typeId, devId):
		valuesDict["state2"] = ""
		valuesDict["type2"] = "auto"
		return valuesDict	
		
	#
	# State based LCD 3rd state clear button clicked
	#
	def uiButtonClicked_State3 (self, valuesDict, typeId, devId):
		valuesDict["state3"] = ""
		valuesDict["type3"] = "auto"
		return valuesDict	
		
	#
	# State based LCD 4th state clear button clicked
	#
	def uiButtonClicked_State4 (self, valuesDict, typeId, devId):
		valuesDict["state4"] = ""
		valuesDict["type4"] = "auto"
		return valuesDict	
		
	#
	# State based LCD 5th state clear button clicked
	#
	def uiButtonClicked_State5 (self, valuesDict, typeId, devId):
		valuesDict["state5"] = ""
		valuesDict["type5"] = "auto"
		return valuesDict	
		
	################################################################################
	# SUPPORT DEBUG ROUTINE - 1.12
	################################################################################	
	
	#
	# Plugin menu: Support log
	#
	def supportLog (self):
		self.showLibraryVersions ()
		
		s = eps.debugHeader("SUPPORT LOG")
		
		# Get plugin prefs
		s += eps.debugHeader ("PLUGIN PREFRENCES", "=")
		for k, v in self.pluginPrefs.iteritems():
			s += eps.debugLine(k + " = " + unicode(v), "=")
			
		s += eps.debugHeaderEx ("=")
		
		# Report on cache
		s += eps.debugHeader ("DEVICE CACHE", "=")
		
		for devId, devProps in self.cache.devices.iteritems():
			s += eps.debugHeaderEx ("*")
			s += eps.debugLine(devProps["name"] + ": " + str(devId) + " - " + devProps["deviceTypeId"], "*")
			s += eps.debugHeaderEx ("*")
			
			s += eps.debugHeaderEx ("-")
			s += eps.debugLine("SUBDEVICES", "-")
			s += eps.debugHeaderEx ("-")
			
			for subDevId, subDevProps in devProps["subDevices"].iteritems():
				s += eps.debugHeaderEx ("+")
				s += eps.debugLine(subDevProps["name"] + ": " + str(devId) + " - " + subDevProps["deviceTypeId"] + " (Var: " + subDevProps["varName"] + ")", "+")
				s += eps.debugHeaderEx ("+")
				
				s += eps.debugLine("WATCHING STATES:", "+")
				
				for z in subDevProps["watchStates"]:
					s += eps.debugLine("     " + z, "+")
					
				s += eps.debugHeaderEx ("+")
					
				s += eps.debugLine("WATCHING PROPERTIES:", "+")
				
				for z in subDevProps["watchProperties"]:
					s += eps.debugLine("     " + z, "+")
					
				if subDevId in indigo.devices:
					d = indigo.devices[subDevId]
					if d.pluginId != self.pluginId:
						s += eps.debugHeaderEx ("!")
						s += eps.debugLine(d.name + ": " + str(d.id) + " - " + d.deviceTypeId, "!")
						s += eps.debugHeaderEx ("!")
					
						s += eps.debugHeaderEx ("-")
						s += eps.debugLine("PREFERENCES", "-")
						s += eps.debugHeaderEx ("-")
			
						for k, v in d.pluginProps.iteritems():
							s += eps.debugLine(k + " = " + unicode(v), "-")
				
						s += eps.debugHeaderEx ("-")
						s += eps.debugLine("STATES", "-")
						s += eps.debugHeaderEx ("-")
			
						for k, v in d.states.iteritems():
							s += eps.debugLine(k + " = " + unicode(v), "-")
						
						s += eps.debugHeaderEx ("-")
						s += eps.debugLine("RAW DUMP", "-")
						s += eps.debugHeaderEx ("-")
						s += unicode(d) + "\n"
				
						s += eps.debugHeaderEx ("-")
					else:
						s += eps.debugHeaderEx ("!")
						s += eps.debugLine("Plugin Device Already Summarized", "+")
						s += eps.debugHeaderEx ("!")
				else:
					s += eps.debugHeaderEx ("!")
					s += eps.debugLine("!!!!!!!!!!!!!!! DEVICE DOES NOT EXIST IN INDIGO !!!!!!!!!!!!!!!", "+")
					s += eps.debugHeaderEx ("!")
				
			s += eps.debugHeaderEx ("-")
		
		
		s += eps.debugHeaderEx ("=")
		
		# Loop through all devices for this plugin and report
		s += eps.debugHeader ("PLUGIN DEVICES", "=")
		
		for dev in indigo.devices.iter(self.pluginId):
			s += eps.debugHeaderEx ("*")
			s += eps.debugLine(dev.name + ": " + str(dev.id) + " - " + dev.deviceTypeId, "*")
			s += eps.debugHeaderEx ("*")
			
			s += eps.debugHeaderEx ("-")
			s += eps.debugLine("PREFERENCES", "-")
			s += eps.debugHeaderEx ("-")
			
			for k, v in dev.pluginProps.iteritems():
				s += eps.debugLine(k + " = " + unicode(v), "-")
				
			s += eps.debugHeaderEx ("-")
			s += eps.debugLine("STATES", "-")
			s += eps.debugHeaderEx ("-")
			
			for k, v in dev.states.iteritems():
				s += eps.debugLine(k + " = " + unicode(v), "-")
				
			s += eps.debugHeaderEx ("-")
			
		s += eps.debugHeaderEx ("=")
		
		
		
		
		indigo.server.log(s)
		
		
	################################################################################
	# UPDATE CHECKS - 1.12
	################################################################################

	def updateCheck (self, onlyNewer = False, force = True):
		try:
			try:
				if self.pluginUrl == "": 
					if force: indigo.server.log ("This plugin currently does not check for newer versions", isError = True)
					return
			except:
				# Normal if pluginUrl hasn't been defined
				if force: indigo.server.log ("This plugin currently does not check for newer versions", isError = True)
				return
			
			d = indigo.server.getTime()
			
			if eps.valueValid (self.pluginPrefs, "latestVersion") == False: self.pluginPrefs["latestVersion"] = False
			
			if force == False and eps.valueValid (self.pluginPrefs, "lastUpdateCheck", True):
				last = datetime.datetime.strptime (self.pluginPrefs["lastUpdateCheck"], "%Y-%m-%d %H:%M:%S")
				lastCheck = dtutil.DateDiff ("hours", d, last)
								
				if self.pluginPrefs["latestVersion"]:
					if lastCheck < 24: return # if last check has us at the latest then only check once a day
				else:
					if lastCheck < 2: return # only check every four hours in case they don't see it in the log
			
			self.debugLog("Checking for updates")

			page = urllib2.urlopen(self.pluginUrl)
			soup = BeautifulSoup(page)
		
			versions = soup.find(string=re.compile("\#Version\|"))
			versionData = unicode(versions)
		
			versionInfo = versionData.split("#Version|")
			newVersion = float(versionInfo[1][:-1])
		
			if newVersion > float(self.pluginVersion):
				self.pluginPrefs["latestVersion"] = False
				indigo.server.log ("Version %s of %s is available, you are currently using %s." % (str(round(newVersion,2)), self.pluginDisplayName, str(round(float(self.pluginVersion), 2))), isError=True)
			
			else:
				self.pluginPrefs["latestVersion"] = True
				if onlyNewer == False: indigo.server.log("%s version %s is the most current version of the plugin" % (self.pluginDisplayName, str(round(float(self.pluginVersion), 2))))
				
			self.pluginPrefs["lastUpdateCheck"] = d.strftime("%Y-%m-%d %H:%M:%S")
			
				
		except Exception as e:
			eps.printException(e)
	
		
		
	################################################################################
	# LEGACY MIGRATED ROUTINES
	################################################################################
	


	

	
