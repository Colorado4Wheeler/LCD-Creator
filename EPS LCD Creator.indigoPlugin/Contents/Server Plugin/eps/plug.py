import datetime
from datetime import timedelta
import time
import indigo
import sys
import re # regular expressions
import eps # 1.13
import dtutil # 1.13

from lcd import lcd

lcdlib = lcd()
parent = None

#
# Definitions
#
defThermostat 	= ["temperatureInput1", "humidity", "setpointHeat", "setpointCool"]
defSprinklers	= ["activeZone", "activeZone.ui"]

defNOAA			= ["currentCondition", "humidity", "windDegrees", "windDirection", "windMPH"]
defWeathersnoop = ["humidity", "weather", "windDirection", "windDirection.ui", "solarRadiation", "temperature_F.ui"] # any .ui here are just so we trigger a state change to calculate other things that don't exist in the weathersnoop device (like "feelslike")
defWUnderground	= ["currentWeather", "precip_1hr", "precip_today", "relativeHumidity", "temp", "foreDay1", "foreDay2", "foreDay3", "foreDay4", "foreHigh1", "foreHigh2", "foreHigh3", "foreHigh4", "foreLow1", "foreLow2", "foreLow3", "foreLow4", "forePop1", "forePop2", "forePop3", "forePop4", "historyHigh", "historyLow", "dewpoint", "feelslike", "windchill", "windDegrees", "windDIR", "windSpeed", "windGust", "pressure", "uv"]

defAlarmClock	= ["durationMinutes","startTime.ui","endTime.ui","timeUntilOn","timeUntilOff"] # 1.1.0 for EPS Alarm Clock

defWeatherEx	= ["hightemp", "lowtemp", "highhumidity", "lowhumidity"] # Device Extension
defThermostatEx	= ["hightemp", "lowtemp", "highhumidity", "lowhumidity", "setModeSetPoint"] # Device Extension
defIrrigationEx	= ["zoneRunTimeRemaining", "scheduleRunTimeRemaining", "pauseTimeRemaining"] # Device Extension

#
# Base
#
def base (self):
	try:
		X = 1
	
	except Exception as e:
		eps.printException(e)

#
# Update the LCD for a watched changed state (ref cache's watchedStateChanged for stateChangedAry)
#
def updateChangedLCD (devChild, stateChangedAry):
	try:
		for pluginDevId, stateProps in stateChangedAry.iteritems():
			for s in stateProps["stateChanges"]:
				if s in devChild.states:
					devParent = indigo.devices[int(pluginDevId)]
				
					# Make sure the state is valid - 1.13
					if eps.valueValid (devChild.states, s) == False:
						indigo.server.log ("The watched state of '%s' on '%s' for LCD device '%s' is not a valid state and won't be converted" % (s, devChild.name, devParent.name), isError=True)
						return
						
					state = getStateDetails (devParent, s)
					if state is None: return # Added in 1.13 to handle invalid states
					
					stateValue = devChild.states[s]
				
					# Convert if required
					if state[3]: stateValue = convertStateValue (devParent, devChild, s, stateValue)
					
					parent.debugLog ("\t%s changed to %s" % (s, unicode(devChild.states[s])))
				
					if state[0]:
						# Convert a string to LCD
						value = lcdlib.stringToLCD (stateValue, state[2], devParent.pluginProps["textspaces"])
						parent.debugLog("\t%s LCD readout string value is %s" % (s, value))
						lcdlib.stringToGraphics (devParent, state[1], value)
					
					else:
						# Converting from a number to LCD
						padCharacter = "0"
						if devParent.pluginProps["spaces"]: padCharacter = " " 
					
						# If this is a set point on a thermostat (or setmodesetpoint on extended), make sure decimals are zero since we can't set fractional temperatures on a thermostat
						if devParent.deviceTypeId == "epslcdth" and (state[1] == "setpointHeat" or state[1] == "setpointCool" or state[1] == "setModeSetPoint"):
							parent.debugLog ("\t\tForcing integer value for set points")
							value = lcdlib.numberToLCD (stateValue, state[2], "round", padCharacter)
						else:
							value = lcdlib.numberToLCD (stateValue, state[2], devParent.pluginProps["decimals"], padCharacter)
					
						parent.debugLog("\t%s LCD readout value is %s" % (s, value))
				
						lcdlib.stringToGraphics (devParent, state[1], value)

	
	except Exception as e:
		eps.printException(e)	
	
	
					
					
#
# Return array of [isString T/F, dest state name, length/digits, conversion required T/F]
#
def getStateDetails (dev, value):
	# Most of our device states should have digits, hidden or otherwise
	d = 4

	try:		
		if "digits" in dev.pluginProps: d = int(dev.pluginProps["digits"])

		#defAlarmClock	= ["durationMinutes","startTime.ui","endTime.ui","timeUntilOn","timeUntilOff"] # 1.1.0 for EPS Alarm Clock
		if dev.deviceTypeId == "epslcdalc": # 1.1.0
			if value == "startTime.ui": return [True, "startTime", d, False]
			if value == "endTime.ui": return [True, "endTime", d, False]
			if value == "durationMinutes": return [False, value, d, False]
		
			parent.debugLog(u"Returning defaults for %s" % value)
			return [True, value, 4, False] # The rest of the state names are a direct match

		if dev.deviceTypeId == "epslcdsb": 
			devChild = indigo.devices[int(dev.pluginProps["device"])]
		
			for i in range (1, 6):
				if dev.pluginProps["state" + str(i)] != "":
					if value == dev.pluginProps["state" + str(i)]: 		
						if eps.valueValid (devChild.states, dev.pluginProps["state" + str(i)]) == False: # 1.13
							indigo.server.log ("State '%s' is not a valid state on '%s', '%s' is unable to convert this value" % (dev.pluginProps["state" + str(i)], devChild.name, dev.name), isError=True)
							return [True, "state" + str(i) + "_", d, False]
					
						if dev.pluginProps["type" + str(i)] == "auto":
							stateValue = devChild.states[dev.pluginProps["state" + str(i)]]
						
							if type(stateValue) is int or type(stateValue) is float or type(stateValue) is long:
								parent.debugLog(u"\tDetermined state %s value is a number" % value)
								return [False, "state" + str(i) + "_", d, False]
							else:
								parent.debugLog(u"\tDetermined state %s value is a %s and will be treated like a string" % (value, type(value)))
								return [True, "state" + str(i) + "_", d, False]
						elif dev.pluginProps["type" + str(i)] == "sectommss" or dev.pluginProps["type" + str(i)] == "sectohhmmss": # 1.1.1 - require a calculation
							return [True, "state" + str(i) + "_", d, True]
						else:
							return [False, "state" + str(i) + "_", d, False]

		if dev.deviceTypeId == "epslcdth": 
			# These will only be returned if there is an Extended Device, none of the other plugins return these states:
			if value == "hightemp": return [False, value, d, False]
			if value == "lowtemp": return [False, value, d, False]
			if value == "highhumidity": return [False, value, d, False]
			if value == "lowhumidity": return [False, value, d, False]
			if value == "setModeSetPoint": return [False, value, d, False]
	
			return [False, value, 4, False] # All thermostat LCD's are numbers and all state names match
	
		if dev.deviceTypeId == "epslcdwe": # Weather LCD
			devChild = indigo.devices[int(dev.pluginProps["device"])]
		
			# These will only be returned if there is an Extended Device, none of the other plugins return these states:
			if value == "hightemp": return [False, value, d, False]
			if value == "lowtemp": return [False, value, d, False]
			if value == "highhumidity": return [False, value, d, False]
			if value == "lowhumidity": return [False, value, d, False]
		
			if devChild.pluginId == "com.fogbert.indigoplugin.wunderground": # Weather Underground plugin		
				if value == "relativeHumidity": return [False, "humidity", d, False]
				if value == "temp": return [False, "temperature", d, False]
				if value == "precip_1hr": return [False, "hourrain", d, False]
				if value == "precip_today": return [False, "dayrain", d, False]
				if value == "currentWeather": return [True, "conditions", d, True]
			
				if value == "foreDay1": return [True, value, d, False]
				if value == "foreDay2": return [True, value, d, False]
				if value == "foreDay3": return [True, value, d, False]
				if value == "foreDay4": return [True, value, d, False]
			
				if value == "historyHigh": return [False, value, d, True]
				if value == "historyLow": return [False, value, d, True]
			
				# 1.1.0 (for values where our state name don't match WUnderground)
				if value == "windDIR": return [True, "windDirection", d, False]
				if value == "uv": return [False, "solarRadiation", d, False]
			
				# Everything else is "forXXX" and is matched in our state names
				return [False, value, d, False]
			
			elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop": # Weathersnoop plugin
				if value == "humidity": return [False, value, d, False]
				if value == "temperature_" + dev.pluginProps["temps"]: return [False, "temperature", d, False]
				if value == "dayRain_" + dev.pluginProps["measures"]: return [False, "dayrain", d, False]
				if value == "rainOneHour_" + dev.pluginProps["measures"]: return [False, "hourrain", d, False]
				if value == "weather": return [True, "conditions", int(dev.pluginProps["conditions"]), True]
			
				# 1.1.0 (for values where our state name don't match WeatherSnoop)
				if value == "dewPoint" + dev.pluginProps["measures"]: return [False, "dewpoint", d, False]
				if value == "temperature_F.ui": 
					parent.debugLog (u"\t### %s being used only as a trigger for 'feelslike' ###" % value)
					return [False, "feelslike", d, True] # Phony state update, we use this to calculate the feels like temperature
				if value == "windChill" + dev.pluginProps["measures"]: return [False, "windchill", d, False]
				if value == "windDirection": return [False, "windDegrees", d, False]
				if value == "windDirection.ui": return [True, "windDirection", d, True]
				if value == "windSpeed_" + dev.pluginProps["speed"]: return [False, "windSpeed", d, False]
				if value == "windGust_" + dev.pluginProps["speed"]: return [False, "windGust", d, False]
				if value == "relativeBarometricPressure_" + dev.pluginProps["pressure"]: return [False, "pressure", d, False]
			
				return [False, value, d, False]
					
		if dev.deviceTypeId == "epslcdws": # DEPRECIATED
			if value == "humidity": return [False, value, d, False]
			if value == "temperature_" + dev.pluginProps["temps"]: return [False, "temperature", d, False]
			if value == "dayRain_" + dev.pluginProps["measures"]: return [False, "dayrain", d, False]
			if value == "rainOneHour_" + dev.pluginProps["measures"]: return [False, "hourrain", d, False]
			if value == "weather": return [True, "conditions", int(dev.pluginProps["conditions"]), True]
		
		if dev.deviceTypeId == "epslcdir":
			if value == "activeZone": return [False, "activezone", d, False]
			if value == "activeZone.ui": return [True, "activezonename", 20, False]
		
			# These will only be returned if there is an Extended Device, none of the other plugins return these states:
			if value == "zoneRunTimeRemaining": return [True, value, d, False]
			if value == "scheduleRunTimeRemaining": return [True, value, d, False]
			if value == "pauseTimeRemaining": return [True, value, d, False]
	
		indigo.server.log(u"Should have gotten state details for %s but it is returning a default instead of %s" % (dev.name, unicode(value)), isError=True)	
		

	
	except Exception as e:
		eps.printException(e)
		
	return [True, value, d, False]

	
#
# Convert state value prior to converting to LCD
#
def convertStateValue (devParent, devChild, state, value):
	try:
		parent.debugLog(u"\t### %s value is being calculated, not derived directly from the state ###" % state)
		if devParent.deviceTypeId == "epslcdws" and state == "weather": # DEPRECIATED
			if int(devParent.pluginProps["conditions"]) == 4: value = stateToWeatherLCD (devChild, state)
	
		if devParent.deviceTypeId == "epslcdsb": # 1.1.1
			for i in range (1, 6):
				if devParent.pluginProps["state" + str(i)] != "":
					if state == devParent.pluginProps["state" + str(i)]: 
						if devParent.pluginProps["type" + str(i)] == "sectommss" or devParent.pluginProps["type" + str(i)] == "sectohhmmss": 
							# Calculate from total seconds elapsed to MM:SS
							s = timedelta(seconds=int(value))
							d = datetime.datetime(1,1,1) + s
						
							lh = d.hour
							lm = d.minute
							ls = d.second

							if devParent.pluginProps["type" + str(i)] == "sectommss":						
								if lh > 1:
									lm = 99
									ls = 99
								if lh == 1:
									if lm < 40: 
										lm = lm + 60 # We max at 99 minutes
									else:
										lm = 99
										ls = 99
								
								value = "%02d:%02d" % (lm, ls)
							else:
								value = "%02d:%02d:%02d" % (lh, lm, ls)
					
		
		if devParent.deviceTypeId == "epslcdwe":
			if devChild.pluginId == "com.fogbert.indigoplugin.wunderground":
				# Catchall to make sure we aren't trying to pass "-999.0" and "-9999.0" as values
				try:
					if int(value) < "-900": value = 0
				except:
					# We'll get this if the value is a string
					value = value
			
			if devChild.pluginId == "com.fogbert.indigoplugin.wunderground" and state == "currentWeather":
				if int(devParent.pluginProps["conditions"]) == 4: value = stateToWeatherLCD (devChild, state)
			
			elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop" and state == "windDirection.ui":
				pattern = re.compile(r"\((\w+)\)")
				value = pattern.findall(value)
				value = value[0]
			
			elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop" and state == "temperature_F.ui":
				measurement = devParent.pluginProps["temps"]
				if float(devChild.states["temperature_" + measurement]) > 50:
					# Use heat index
					value = float(devChild.states["heatIndex_" + measurement])
				else:
					# Use wind chill
					value = float(devChild.states["windChill_" + measurement])
			
			
			elif devChild.pluginId == "com.perceptiveautomation.indigoplugin.weathersnoop" and state == "weather":
				if int(devParent.pluginProps["conditions"]) == 4: value = stateToWeatherLCD (devChild, state)

	
	except Exception as e:
		eps.printException(e)
		
	
	return value
	
#
# Special weather short strings
#
def stateToWeatherLCD (dev, state):
	try:
		if state in dev.states:
			value = dev.states[state]
		else:
			indigo.server.log(u"Unable to convert long weather condition to short condition because the state %s does not exist in %s" % (state, dev.name), isError = True)
			return "Err"
	
		if value == "Partly Cloudy": value = "P.CDY"
		if value == "Mostly Cloudy": value = "M.CDY"
		if value == "Clear": value = "CLEA"
		if value == "Thunderstorm": value = "T.STM"
		if value == "Overcast": value = "OVER"
		if value == "Rain": value = "RAIN"
		if value == "Scattered Clouds": value = "S.CLD"	

	
	except Exception as e:
		eps.printException(e)
		
		
	return value
	
	

	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	
	