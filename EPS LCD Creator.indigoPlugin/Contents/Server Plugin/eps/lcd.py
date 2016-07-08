import indigo
import string

class lcd:

	#
	# Initialize the class
	#
	def __init__ (self):
		self.version = "3.0.0"
		
	#
	# Print library version
	#
	def libVersion (self):
		indigo.server.log (u"##### EPS LCD %s #####" % self.version)
		
	#
	# Convert a string into an LCD state
	#
	def stringToLCD (self, value, length, padLeft = False):
		isError = False
		
		try:
			# In case we need comparisons later
			origValue = value
		
			# Only literal graphics have mixed case, dynamic words are always upper
			value = unicode(value).upper()
			
			# See if there are any special characters (like . :) that allow us to extend length by 1 because these characters are joined with their predecessor
			dec = string.find (value, '.')
			if dec > -1 : length = length + 1
			
			col = string.find (value, ':')
			if col > -1 : length = length + 1
				
			# See if we are already capped on length
			if len(value) > length:
				value = value[:length]
				return value
			if len(value) == length:
				return value
			
			# If we got here then our value is shorter than our max, pad it out and return it
			if padLeft:
				value = self.padString (" ", value, length, False, True)
			else:
				value = self.padString (" ", value, length, True, False)
					
			return value
		except:
			indigo.server.log ("Trying to convert string value failed, is this really a string?", isError = True)
			isError = True
			
		if isError:
			ret = "Err"
			for i in range (2, length + 1): # So we return a value of the exact length requested
				ret += " "
			
			#raise	
			return ret
	
	#
	# Convert a number to LCD state
	#	
	def numberToLCD (self, value, digits, decimalsStr, padCharacter = "0"):
		# Verify we are dealing with something real (1.1.0)
		if unicode(value) == "": value = "0"
		
		# In case we need comparisons later
		origValue = value
		
		# A double failsafe (1.1.0)
		try:
			value = float(value) # Failsafe
		except:
			value = 0
			
		# Get the devices decimal options
		rounding = 0 # Default to round to nearest whole number (decimals = round or single)
		
		if decimalsStr == "actual": 
			rounding = digits	
		elif decimalsStr == "one": 
			rounding = 1
		elif decimalsStr == "two": 
			rounding = 2
		elif decimalsStr == "three": 
			rounding = 3
			
		# If the rounding is the same as number of digits then subtract one because we can never start with a decimal
		if rounding >= digits:
			rounding = digits - 1
		
		value = round (value,rounding) # Always 1 less than max because we cannot start with a decimal
		value = str(value) # From here on out we are dealing with a string
		
		# Pad the string with zeros, bearing in mind that although a decimal is a character in the string it does
		# not count as one in the calculation since our graphics incorporate that
		fullLen = len(value)
		calcLen = len(value)
		
		dec = string.find (value, '.')
		if dec > -1 : calcLen = calcLen -1
		
		# If our setting is for "round" and not "single" then strip the decimal out
		if decimalsStr == "round":
			if dec > -1:
				value = value[:dec] 
				dec = -1 # Force it so when we reference it again there is no decimal
				
		# If we are already at our max digits then we can return now (we shouldn't be over since round fixes that)
		if calcLen == digits: return value
		
		# Pad the number as configured - if no decimal then only left, if decimal then left or right
		if dec > -1:
			# See how many chars pre and post decimal
			calcValue = value.split(".")
			
			if decimalsStr == "actual" or decimalsStr == "single":
				value = self.padString (padCharacter, value, digits + 1, False, True)
			else:
				value = self.padString (padCharacter, value, digits + 1, True, False)	 
			
			
		else:
			value = self.padString (padCharacter, value, digits, False, True)
		
		return value
		
		
	#
	# Pad a string with additional characters
	#
	def padString (self, pad, value, maxLen, padRight, padLeft):
		strLen = len(value)
		padChars = maxLen - strLen
		
		newValue = ""
		for i in range (0, padChars):
			newValue = newValue + pad
		
		if padLeft:
			newValue = newValue + value
			return newValue
			
		if padRight:
			newValue = value + newValue
			return newValue	
	
	#
	# Clear states
	#
	def clearStates (self, lcddev, stateprefix, loops):
		for i in range (0, loops) :
			statename = stateprefix + str(i + 1)
			if statename in lcddev.states:
				#indigo.server.log(statename)
				lcddev.updateStateOnServer(statename, "")
			
	#
	# Convert string to graphics names
	#
	def stringToGraphics (self, lcddev, stateprefix, value):
		curpos = 0
				
		for i in range (0, len(value)) :
			g = ""
			
			if value[i] == ".": 
				continue
				
			if value[i] == ":": 
				continue
				
			if value[i] == "'": 
				continue
				
			elif value[i] == " ": 
				g = "SPC"
					
			elif value[i] == "-": 
				g = "HYP"
				
			elif value[i] == "&": # 1.1.0
				g = "AND"
				
			elif value[i] == "%": # 1.1.0
				g = "PER"
				
			elif value[i] == "+": # 1.1.0
				g = "PLU"
				
			elif value[i] == "&": # 1.1.0 
				g = "AND"
					
			else:
				g = value[i]
				
					
			# Account for special characters
			if i < (len(value) - 1):
				if value[i + 1] == ".": g = g + "DOT"
				if value[i + 1] == ":": g = g + "COL"
				if value[i + 1] == "'": g = g + "APO" # 1.1.0, removed from being its own character above
			
			statename = stateprefix + str(curpos + 1)
			if statename in lcddev.states:
				#indigo.server.log("Found " + statename + " in states...")
				lcddev.updateStateOnServer(statename, g)
				#indigo.server.log(g)
				x = 1
			else:
				indigo.server.log("Could not find " + statename + " in states, the state we are getting the value from shouldn't be reporting this many characters", isError=True)
				
			curpos = curpos + 1
		
		
		
		
		
		
		