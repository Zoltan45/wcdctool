#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# ------------------------------------------------------------------------------
#                                                                              -
#  Watcom Decompilation Tool (wcdctool)                                        -
#                                                                              -
#  Created by Fonic (https://github.com/fonic)                                 -
#  Date modified: 12/18/19                                                     -
#  Date started:  06/20/19                                                     -
#                                                                              -
# ------------------------------------------------------------------------------



# ------------------------------------------------------------------------------
#                                                                              -
#  Imports                                                                     -
#                                                                              -
# ------------------------------------------------------------------------------

# Import dependencies
try:
	import os
	import sys
	import re
	import subprocess
	import tempfile
	import ntpath
	import shutil
	from collections import OrderedDict
	from modules.ArgumentParser import ArgumentParser
except ImportError as error:
	sys.stderr.write("Failed to initialize application:\n%s\n" % error)
	sys.exit(1)

# Check Python version
if (sys.version_info < (3, 6, 0)):
	sys.stderr.write("This application requires Python version 3.6.0 or higher to run.\n")
	sys.exit(1)



# ------------------------------------------------------------------------------
#                                                                              -
#  Functions                                                                   -
#                                                                              -
# ------------------------------------------------------------------------------

# Text output / logging
# NOTE: Plaintext log may be obtained by ignoring 'esc1'+'esc2' of log items;
#       print_null may be used to silence out/log, i.e. out=print_null / log=print_null
print_log = []
print_out = sys.stdout

class print_null(object): # https://stackoverflow.com/a/2929954
	def write(self, *_): pass
	def append(self, *_): pass

def print_text(esc1, text, esc2, end, out, log):
	log.append(OrderedDict([("esc1", esc1), ("text", text), ("esc2", esc2), ("end", end)]))
	#print(esc1 + text + esc2, end=end) if (text != "") else print(end=end)
	out.write(esc1 + text + esc2 + end)

def print_normal(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[0;37m", text, "\033[0m", end, out, log)

def print_light(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1m", text, "\033[0m", end, out, log)

def print_hilite(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1;34m", text, "\033[0m", end, out, log)

def print_dark(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1;30m", text, "\033[0m", end, out, log)

def print_good(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1;32m", text, "\033[0m", end, out, log)

def print_warn(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1;33m", text, "\033[0m", end, out, log)

def print_error(text="", end="\n", out=print_out, log=print_log):
	print_text("\033[1;31m", text, "\033[0m", end, out, log)


# Recursively generates pretty print of iterable (dict, tuple, list), optionally adds technical details
# TODO: not for this, but for other projects: add support to pprint objects:
#       for member in dir(object):
#           value = getattr(object, member)
def generate_pprint(var, level=0, indent="    ", maxlevel=None, technical=True, justify=True, exclude_ids=[]):
	result = []

	# Recursion limit reached?
	if (maxlevel != None and level > maxlevel):
		#result.append("%s<recursion limit reached>" % (indent * level))
		return result

	# Current variable excluded?
	if (id(var) in exclude_ids):
		#result.append("%s<current item is excluded>" % (indent * level))
		return result

	# Determine keys to process; this exploits the fact that dicts and tuples/lists are essentially the same,
	# i.e. a storage of key-value-pairs; where dicts have named keys, tuples/lists have indices as keys
	if (isinstance(var, dict)):
		keys = var.keys()
	elif (isinstance(var, tuple) or isinstance(var, list)):
		keys = range(0, len(var))
	else:
		print_error("Invalid variable type '%s'" % type(var))
		return result

	# Justify output?
	ktmp1 = ktmp2 = "%s"
	if (justify == True):
		maxlen = 0
		for key in keys:
			klen = len(str(key))
			if (klen > maxlen):
				maxlen = klen
		ktmp1 = "%-" + str(maxlen+3) + "s"
		ktmp2 = "%-" + str(maxlen+1) + "s"

	# Process keys
	for key in keys:
		out = ("%s" + ktmp1) % (indent * level, "'" + str(key) + "':") if (technical == True and isinstance(key, str)) else ("%s" + ktmp2) % (indent * level, str(key) + ":")
		if (isinstance(var[key], dict) or isinstance(var[key], tuple) or isinstance(var[key], list)):
			out += " <%s, %d items>" % (type(var[key]).__name__, len(var[key])) if (technical == True) else ""
		elif (isinstance(var[key], bytes)):
			out += " <%d bytes>" % len(var[key])
		elif (isinstance(var[key], bool)): # required as 'bool' also registers as 'int', thus next if would catch bool and interpret it as number
			out += " %s" % var[key]
		elif (isinstance(var[key], int)):
			out += " %d (0x%x)" % (var[key], var[key])
		elif (isinstance(var[key], str)):
			out += " '%s'" % repr(var[key])[1:-1] if (technical == True) else " " + repr(var[key])[1:-1]
		else:
			out += " '%s'" % str(var[key]) if (technical == True) else " " + str(var[key])
		result.append(out)
		if (isinstance(var[key], dict) or isinstance(var[key], tuple) or isinstance(var[key], list)):
			if (len(var[key]) == 0):
				if (not technical):
					result[-1] += " <empty>"
				continue
			result += generate_pprint(var[key], level=level+1, indent=indent, maxlevel=maxlevel, technical=technical, justify=justify, exclude_ids=exclude_ids)

	return result


# Writes content to file; content may be provided as list/tuple of strings (will be joined using
# joinstr and written as text), as string (will be written as text) or as bytes (will be written
# as binary data); template is used to generate file path/name
def write_file(template, filename, content, joinstr=os.linesep):
	path = template % filename
	dir = os.path.dirname(path)
	try:
		if (dir != ""):
			os.makedirs(dir, exist_ok=True)

		if (isinstance(content, tuple) or isinstance(content, list)):
			with open(path, "w") as file:
				file.write(str.join(joinstr, content))
		elif (isinstance(content, str)):
			with open(path, "w") as file:
				file.write(content)
		elif (isinstance(content, bytes)):
			with open(path, "wb") as file:
				file.write(content)
		else:
			print_error("Invalid content type '%s'" % type(content))
			return False

		return True
	except Exception as exception:
		print_error("Error: %s" % str(exception))
		return False


# Checks if specified dictionary path exists (https://stackoverflow.com/a/43491315)
def dict_path_exists(var, *keys):
	if (not isinstance(var, dict)):
		print_error("Invalid variable type '%s'" % type(var))
		return None
	if (len(keys) == 0):
		print_error("No key(s) specified")
		return None

	_var = var
	for key in keys:
		try:
			_var = _var[key]
		except KeyError:
			return False
	return True



# ------------------------------------------------------------------------------
#                                                                              -
#  Wdump Parser                                                                -
#                                                                              -
# ------------------------------------------------------------------------------

# Splits key value pair of wdump output line; wdump format: 'key = value', e.g. 'file offset = 0000F474H'
# NOTE: whitespace in line needs to be reduced to single characters prior to calling this
# NOTE: key regex is non-greedy, e.g. 'offset = 1234H = 5678H' -> ('offset', '1234H = 5678H')
def wdump_split_keyval(line):
	match = re.match("^(.+?) = (.+)$", line)
	if (match):
		key = match.group(1).lower()
		value = match.group(2)
		if (re.match("^[0-9a-fA-F]+H$", value)):
			value = int(value[0:-1], 16)
		return key, value
	return None, None


# Decodes wdump section data
def wdump_decode_data(section):

	#                                 DOS EXE Header
	# ==============================================================================
	# length of load module mod 200H                       =     008CH
	# number of 200H pages in load module                  =     0017H
	# ...
	#
	# segment:offset
	#   0000:0020   0000:0028   0000:098C   0000:0994   0000:09A0   0000:09A6
	#   0000:09AA   0000:09AE   0000:09B4   0000:09B6   0000:09F1   01BD:0000
	#   ...
	#
	# load module =
	# 0000:  CC EB FD 90 90 90 90 00  53 52 56 57 B8 22 00 E8            SRVW "
	# 0010:  AA 00 85 C0 74 24 BF EC  03 89 C6 57 AC 88 05 47        t$     W   G
	# 0020:  3C 00 75 F8 5F 89 F8 BA  31 00 E8 EC 00 89 F8 E8    < u _   1
	# ...
	#
	# Additional file data follows DOS executable.
	#
	if (section["name"].startswith("DOS EXE Header")):
		decoded_data = OrderedDict()
		for line in section["data"]:
			line2 = str.join(" ", line.split())
			if (line2 == "segment:offset" or line2 == "load module ="):
				break
			key, value = wdump_split_keyval(line2)
			if (key != None and value != None):
				decoded_data[key] = value
				continue
			print_warn("invalid data: '%s'" % line2)


	#                            DOS/16M EXE Header - BW
	# ==============================================================================
	# file offset = 0000F474H
	#
	#                               DOS/16M EXE Header
	# ==============================================================================
	# length of load module mod 200H                       =     01E0H
	# number of 200H pages in load module                  =     00B8H
	# ...
	# GLU version                                          = 2. 72
	# original name: 4GWPRO.EXP
	#
	# GDT selectors:
	#                                 Size in    Size in
	# Sel #    Access    File offset   File       Memory     DPL    Present    Flags
	# -----    ------    -----------   -------    -------    ---    -------    -----
	# 0080      ER         00F564       05F90      05F90     0         1
	# 0088      ER         0154F4       0C1C0      0C1C0     0         1
	# ...
	#
	# Relocations selector:offset
	#
	# 0080:054A 0080:057B 0080:05B9 0080:073F
	# 0080:079C 0080:095C 0080:0B76 0080:0BF9
	# ...
	#
	# Load selector = 0080
	#
	# 0000:  E8 6D 05 00 E8 69 05 01  E8 65 05 02 E8 61 05 03     m   i   e   a
	# 0010:  E8 5D 05 04 E8 59 05 05  E8 55 05 06 E8 51 05 07     ]   Y   U   Q
	# ...
	# NOTE: everything after 'GDT selectors:' is ignored
	elif (section["name"].startswith("DOS/16M EXE Header")):
		decoded_data = OrderedDict()
		for line in section["data"]:
			line2 = str.join(" ", line.split())
			if (line2 == "GDT selectors:"):
				break
			if (line2.startswith("original name:")):
				key, value = [ item.strip() for item in line2.split(":", 1) ]
				decoded_data[key] = value
				continue
			key, value = wdump_split_keyval(line2)
			if (key != None and value != None):
				decoded_data[key] = value
				continue
			print_warn("invalid data: '%s'" % line2)


	#                       Linear EXE Header (OS/2 V2.x) - LE
	# ==============================================================================
	# file offset = 00002C90H
	#
	# byte order (0==little endian, 1==big endian)      =       00H
	# word order       "                "               =       00H
	# ...
	# Module Flags = PROGRAM | WINDOWCOMPAT
	#
	elif (section["name"].startswith("Linear EXE Header (OS/2 V2.x) - LE")):
		decoded_data = OrderedDict()
		for line in section["data"]:
			line2 = str.join(" ", line.split())
			key, value = wdump_split_keyval(line2)
			if (key != None and value != None):
				decoded_data[key] = value
				continue
			print_warn("invalid data: '%s'" % line2)


	#                                  Object Table
	# ==============================================================================
	# object  1: virtual memory size             = 0003B2D5H
	#           relocation base address          = 00010000H
	#           object flag bits                 = 00002045H
	#           object page table index          = 00000001H
	#           # of object page table entries   = 0000003CH
	#           reserved                         = 00000000H
	#           flags = READABLE|EXECUTABLE|PRELOAD|BIG
	#     page #   1  map page = 000001H file ofs = 0002A400H flgs = 00H Valid
	#
	# segment # 1   offset: 0002A400
	# ===========
	# 0000:  CC EB FD 90 90 90 90 90  90 90 90 90 90 90 90 90
	# 0010:  53 51 52 56 57 55 8B 1D  48 98 04 00 89 C6 83 3D    SQRVWU  H      =
	# ...
	# 0FF0:  04 00 E8 AA BA 02 00 83  C4 0C 89 F8 E8 C2 BA 02
	#
	#
	#     page #   2  map page = 000002H file ofs = 0002B400H flgs = 00H Valid
	#
	# segment # 2   offset: 0002B400
	# ===========
	# 0000:  00 80 BC 24 C4 00 00 00  00 0F 84 51 01 00 00 8B       $       Q
	# 0010:  84 24 C0 00 00 00 BF 01  00 00 00 8B 00 8B 1D A4     $
	# ...
	elif (section["name"].startswith("Object Table")):
		decoded_data = OrderedDict()
		current_object = None
		current_page = None
		current_segment = None
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			# Skip '='-only lines
			if (re.match("^[=]+$", line2)):
				continue

			# New object
			match = re.match("^object ([0-9]+): (.+)$", line2)
			if (match):
				num = int(match.group(1))
				decoded_data[num] = OrderedDict([("num", num)])
				current_object = decoded_data[num]
				line2 = match.group(2)

			# New page
			match = re.match("^page # ([0-9]+) map page = ([0-9a-fA-F]+)H file ofs = ([0-9a-fA-F]+)H flgs = ([0-9a-fA-F]+)H (.+)$", line2)
			if (match):
				if (current_object == None):
					print_warn("stray page: '%s'" % line2)
					continue
				if (not "pages" in current_object):
					current_object["pages"] = OrderedDict()
				num = int(match.group(1))
				current_object["pages"][num] = OrderedDict([("num", num), ("map page", int(match.group(2), 16)), ("file offset", int(match.group(3), 16)), ("flags", int(match.group(4), 16)), ("valid", True if (match.group(5) == "Valid") else False), ("segments", OrderedDict())])
				current_page = current_object["pages"][num]
				continue

			# New segment
			match = re.match("^segment # ([0-9]+) offset: ([0-9a-fA-F]+)$", line2)
			if (match):
				if (current_page == None):
					print_warn("stray segment: '%s'" % line2)
					continue
				#current_page["segments"].append( { "num": int(match.group(1)), "offset": int(match.group(2), 16), "data": b'' } )
				#current_segment = current_page["segments"][-1]
				num = int(match.group(1))
				current_page["segments"][num] = OrderedDict([("num", num), ("offset", int(match.group(2), 16)), ("data", b'')])
				current_segment = current_page["segments"][num]
				continue

			# Segment data (NOTE: matching against original line here to correctly capture hex data)
			match = re.match("^([0-9a-fA-F]+):  ([0-9a-fA-F ]+)    (.{16})$", line)
			if (match):
				if (current_segment == None):
					print_warn("stray segment data: '%s'" % line2)
					continue
				hexdata = str.join(" ", match.group(2).split())
				current_segment["data"] += bytes.fromhex(hexdata)
				continue

			# Object data
			if (current_object == None):
				print_warn("stray object data: '%s'" % line2)
				continue
			key, value = wdump_split_keyval(line2)
			if (key != None and value != None):
				current_object[key] = value
				continue

			print_warn("invalid data: '%s'" % line2)


	#                              Resident Names Table
	# ==============================================================================
	# ordinal 0000: mk1
	#
	elif (section["name"].startswith("Resident Names Table")):
		decoded_data = str.join("", section["data"])


	#                                Fixup Page Table
	# ==============================================================================
	#   0:00000000       1:00000554       2:00000969       3:00000CD3
	#   4:00000F80       5:00001849       6:00002292       7:00002967
	#   ...
	#  28:0002716E      29:00027192      30:00027210
	#
	elif (section["name"].startswith("Fixup Page Table")):
		decoded_data = OrderedDict()
		for line in section["data"]:
			line2 = str.join(" ", line.split())
			for data in line2.split(" "):
				data = data.split(":")
				if (len(data) != 2):
					print_warn("invalid data: '%s'" % line2)
					continue
				decoded_data[int(data[0])] = int(data[1], 16)


	#                               Fixup Record Table
	# ==============================================================================
	# Source  Target
	#   type  flags
	#   ====  ====
	#    07    10   src off = 09B7   object #    = 02   target off       = 000498BA
	#    07    10   src off = 09FF   object #    = 02   target off       = 000498B0
	#    ...
	#    07    10   src off = 07DC   object #    = 01   target off       = 0003B2AC
	#
	# NOTE: not sure if source type, target flags and object # are decimal or hex; all decimal for now
	elif (section["name"].startswith("Fixup Record Table")):
		decoded_data = []
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			match = re.match("^([0-9]+) ([0-9]+) src off = ([0-9a-fA-F ]+) object # = ([0-9]+) target off = ([0-9a-fA-F ]+)$", line2)
			if (match):
				decoded_data.append(OrderedDict([("source type", int(match.group(1))), ("target flags", int(match.group(2))), ("source offset", int(match.group(3), 16)), ("object", int(match.group(4))), ("target offset", int(match.group(5), 16))]))
				continue

			if (line2 == "Source Target" or line2 == "type flags" or line2 == "==== ===="):
				continue

			print_warn("invalid data: '%s'" % line2)


	#                            Nonresident Names Table
	# ==============================================================================
	#
	# NOTE: not spotted with any data yet
	elif (section["name"].startswith("Nonresident Names Table")):
		decoded_data = str.join("", section["data"])


	#                               Master Debug Info
	# ==============================================================================
	# EXE major                 =       03H
	# EXE minor                 =       00H
	# ...
	#
	# Languages
	# =========
	# C
	# CPP
	#
	# Segments
	# ========
	# 0001
	# 0002
	#
	# Section 0 (off=000ABC09)
	# =========================
	#   Module info offset   = 00033BDEH
	#   Global info offset   = 000351FDH
	#   ...
	elif (section["name"].startswith("Master Debug Info")):
		decoded_data = OrderedDict()
		target = decoded_data
		for i in range(0, len(section["data"])):
			line = section["data"][i]
			line2 = str.join(" ", line.split())

			# Skip '='-only lines
			if (re.match("^[=]+$", line2)):
				continue

			# Handle subsections
			if (i < len(section["data"])-1 and re.match("^[=]+$", str.join(" ", section["data"][i+1].split()))):
				if (line2 == "Languages"):
					decoded_data["languages"] = []
					target = decoded_data["languages"]
					continue
				if (line2 == "Segments"):
					decoded_data["segments"] = []
					target = decoded_data["segments"]
					continue
				match = re.match("^Section ([0-9]+) \(off=([0-9a-fA-F]+)\)$", line2)
				if (match):
					if (not "sections" in decoded_data):
						decoded_data["sections"] = OrderedDict()
					num = int(match.group(1))
					decoded_data["sections"][num] = OrderedDict([("num", num), ("offset", int(match.group(2), 16))])
					target = decoded_data["sections"][num]
					continue

			# Decide how to append data based on target type
			if (isinstance(target, list)):
				target.append(line2)
			elif (isinstance(target, dict)):
				key, value = wdump_split_keyval(line2)
				if (key != None and value != None):
					target[key] = value
					continue
				print_warn("invalid data: '%s'" % line2)


	#                            Module Info (section 0)
	# ==============================================================================
	#   0) Name:   D:\IBM\MKTRIL\SOURCE\input.c
	#      Language is C
	#      Locals: num = 1, offset = 00000012H
	#      Types:  num = 1, offset = 00000062H
	#      Lines:  num = 1, offset = 000000B2H
	#
	#    *** Locals ***
	#    ==============
	#       Data 0:  offset 00000236
	#         0000: MODULE_386
	#           "JoyThresholdY" addr = 0003:00059610,  type = 81
	#         0016: MODULE_386
	#           "JoyThresholdX" addr = 0003:00059618,  type = 82
	#         ...
	#         03BB: LOCAL
	#           address: BP_OFFSET_BYTE( C0 )
	#           name = "outregs",  type = 115
	#
	#    *** Line Numbers ***
	#    ====================
	#       1 offset entries:
	#         offset 0 = 00010894H
	#         offset 1 = 00010EEEH
	#       -------------------------------------
	#       Data 0: offset 00010894H, addr info off = 0000000EH, num = 32
	#         number =   93,  code offset = 00000008H
	#         number =  112,  code offset = 00000016H
	#         ...
	#         number =  172,  code offset = 0000019CH
	#       -------------------------------------
	#       Data 0: offset 00010894H, addr info off = 0000000EH, num = 32
	#         number =  174,  code offset = 000001A6H
	#         number =  176,  code offset = 000001BBH
	#         ...
	#
	#     *** Types ***
	#     =============
	#       Data 0:  offset 00007170
	#         0000: cue table offset=00000513
	#         0006: SCOPE(1)
	#           "struct"
	#         ...
	#         0509: NAME(115)
	#           "REGS"  type idx = 114  scope idx = 2
	#
	# NOTE: 'Types' appears after 'Line Numbers', contrary to order at beginning
	# NOTE: 'num' in this section means 'count', e.g. 'Lines:  num = 1, ...' means there's one 'Lines Numbers' section
	elif (section["name"].startswith("Module Info")):
		decoded_data = OrderedDict()
		current_module = None
		skip_until_next_module = False
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			# Skip subsections '*** Locals ***', '*** Types ***' and '*** Line Numbers ***'
			if (line2 == "*** Locals ***" or line2 == "*** Types ***" or line2 == "*** Line Numbers ***"):
				skip_until_next_module = True
				continue

			# New module
			match = re.match("^([0-9]+)\) Name: (.+)$", line2)
			if (match):
				num = int(match.group(1))
				decoded_data[num] = OrderedDict([("num", num), ("name", match.group(2)), ("language", None), ("locals", OrderedDict()), ("types", OrderedDict()), ("lines", OrderedDict())])
				current_module = decoded_data[num]
				skip_until_next_module = False
				continue
			elif (skip_until_next_module):
				continue

			# Check if within module
			if (current_module == None):
				print_warn("stray module data: '%s'" % line2)
				continue

			# Module data
			match = re.match("^Language is (.+)$", line2)
			if (match):
				current_module["language"] = match.group(1)
				continue
			match = re.match("^(.+): num = ([0-9]+), offset = ([0-9a-fA-F]+)H$", line2)
			if (match):
				key = match.group(1).lower()
				if (not key in current_module):
					print_warn("invalid module data: '%s'" % line2)
					continue
				current_module[key]["count"] = int(match.group(2))
				current_module[key]["offset"] = int(match.group(3), 16)
				continue

			print_warn("invalid data: '%s'" % line2)


	#                            Global Info (section 0)
	# ==============================================================================
	#   Name:  PackJoyButtons_
	#     address      = 0001:00000466
	#     module index = 0
	#     kind:          (code)
	#   Name:  _pTopOfHeap
	#     address      = 0003:0005983C
	#     module index = 100
	#     kind:          (static pubdef) (data)
	# NOTE: 'segment' here seems to correspond to 'object' for Linear Executables
	# NOTE: not exactly sure what global names like 'W?smp$n[]pn$_SAMPLE$$' mean; for sure is that name is between '?' and '$', i.e. 'smp' in this example
	elif (section["name"].startswith("Global Info")):
		decoded_data = []
		current_global = None
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			# New global
			match = re.match("^Name: (.+)$", line2)
			if (match):
				name = match.group(1)
				match = re.match("^W\?([^$]+)\$", name)
				if (match):
					name = match.group(1)
				decoded_data.append(OrderedDict([("name", name), ("module", None), ("segment", None), ("offset", None), ("type", None)]))
				current_global = decoded_data[-1]
				continue

			# Check if within global
			if (current_global == None):
				print_warn("stray global data: '%s'" % line2)
				continue

			# Global data
			match = re.match("^address = ([0-9]+):([0-9a-fA-F]+)$", line2)
			if (match):
				current_global["segment"] = int(match.group(1))
				current_global["offset"] = int(match.group(2), 16)
				continue
			match = re.match("^module index = ([0-9]+)$", line2)
			if (match):
				current_global["module"] = int(match.group(1))
				continue
			match = re.match("^kind: (.*)$", line2)
			if (match):
				if (match.group(1).endswith("(code)")):
					current_global["type"] = "code"
				elif (match.group(1).endswith("(data)")):
					current_global["type"] = "data"
				else:
					print_warn("invalid global kind: '%s'" % line2)
					current_global["type"] = "unknown"
				continue

			print_warn("invalid data: '%s'" % line2)


	#                             Addr Info (section 0)
	# ==============================================================================
	#  Base:  fileoff = 00000000H   seg = 0001H,  off = 00000000H
	#      0) fileoff = 00000008H,  Size = 00000010H @00000000H,  mod_index = 75
	#      1) fileoff = 0000000EH,  Size = 00003921H @00000010H,  mod_index = 0
	#      ...
	#  Base:  fileoff = 000003E0H   seg = 0002H,  off = 00000000H
	#      0) fileoff = 000003E8H,  Size = 00000004H @00000000H,  mod_index = 75
	#      1) fileoff = 000003EEH,  Size = 000006F0H @00000004H,  mod_index = 0
	#      ...
	# NOTE: '@[0-9a-fA-F]H' is offset of module within segment
	# NOTE: 'segment' here seems to correspond to 'object' for Linear Executables
	elif (section["name"].startswith("Addr Info")):
		decoded_data = []
		current_block = None
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			# New block
			match = re.match("^Base: fileoff = ([0-9a-fA-F]+)H seg = ([0-9a-fA-F]+)H, off = ([0-9a-fA-F]+)H$", line2)
			if (match):
				decoded_data.append(OrderedDict([("file offset", int(match.group(1), 16)), ("segment", int(match.group(2), 16)), ("offset", int(match.group(3), 16)), ("entries", OrderedDict())]))
				current_block = decoded_data[-1]
				continue

			# Check if within block
			if (current_block == None):
				print_warn("stray block data: '%s'" % line2)
				continue

			# Block data
			match = re.match("^([0-9]+)\) fileoff = ([0-9a-fA-F]+)H, Size = ([0-9a-fA-F]+)H @([0-9a-fA-F]+)H, mod_index = ([0-9]+)$", line2)
			if (match):
				num = int(match.group(1))
				#current_block["entries"][num] = OrderedDict([("num", num), ("file offset", int(match.group(2), 16)), ("size", int(match.group(3), 16)), ("size@", int(match.group(4), 16)), ("module", int(match.group(5)))])
				current_block["entries"][num] = OrderedDict([("num", num), ("file offset", int(match.group(2), 16)), ("size", int(match.group(3), 16)), ("offset", int(match.group(4), 16)), ("module", int(match.group(5)))])
				continue

			print_warn("invalid data: '%s'" % line2)


	#                                  Object Hints
	# ==============================================================================
	#   Object 1:
	#     0) offset = 00003931H, size = 00000008H, type = data, subtype = dwords, comment = Presumably two DWORDs
	#     1) offset = 0002CCFAH, size = 00000076H, type = data, subtype = string, comment = Watcom copyright notice
	#     ...
	#   Object 2:
	#     0) offset = 00000004H, size = 000006F0H, type = data, subtype = strings, comment = Strings
	#     1) offset = 00009A18H, size = 00000A1CH, type = data, subtype = auto, comment = Strings (auto-detection)
	#     ...
	# NOTE: not native wdump, added specifically for wcdctool to support user-specified object hints to aid disassembly
	# NOTE: 'comment' has to be last (see special handling below)
	elif (section["name"].startswith("Object Hints")):
		decoded_data = OrderedDict()
		current_block = None
		for line in section["data"]:
			line2 = str.join(" ", line.split())

			# Comment
			if (line2.startswith("#")):
				continue

			# New block
			match = re.match("^Object ([0-9]+):$", line2)
			if (match):
				objnum = int(match.group(1))
				decoded_data[objnum] = (OrderedDict([("objnum", objnum), ("entries", OrderedDict())]))
				current_block = decoded_data[objnum]
				continue

			# Check if within block
			if (current_block == None):
				print_warn("stray block data: '%s'" % line2)
				continue

			# Block data
			match = re.match("^([0-9]+)\) offset = ([0-9a-fA-F]+)H, size = ([0-9a-fA-F]+)H, type = (.+?)(, .*)?$", line2)
			if (match):
				num = int(match.group(1))
				offset = int(match.group(2), 16)
				size = int(match.group(3), 16)
				type = match.group(4)
				tail = match.group(5)

				# Identify and store any key-value pairs found in tail
				keyvals = OrderedDict()
				if (tail != None):
					for item in tail.split(", "):
						if (item == ""):
							continue
						(key, value) = wdump_split_keyval(item)
						if (key == "comment"): # special handling of key 'comment': consume everything after '=' as value, break loop -> allows comments to contain ','
							match = re.search("comment = (.+)", tail)
							keyvals[key] = match.group(1)
							break
						elif (key != None and value != None):
							keyvals[key] = value
						else:
							print_warn("invalid key-value pair '%s': '%s'" % (item, line2))

				# Sanity checks
				if (type == "data"):
					if (not "subtype" in keyvals):
						print_warn("invalid entry: type 'data' requires 'subtype = ...': '%s'" % line2)
						continue
				else:
					print_warn("invalid entry: invalid type '%s': '%s'" % (type, line2))
					continue

				# Store entry
				current_block["entries"][num] = OrderedDict([("num", num), ("offset", offset), ("size", size), ("type", type)] + list(keyvals.items()))
				continue

			print_warn("invalid entry: '%s'" % line2)


	#                              <Unknown section>
	# ==============================================================================
	else:
		print_warn("no decode rule for section '%s'" % section["name"])
		decoded_data = section["data"]


	# Replace section data with decoded data
	section["data"] = decoded_data


# Parses wdump output, returns parsed representation of output
def wdump_parse_output(input_file, wdump_exec, wdump_output, wdump_add_output, outfile_template):
	print_light("Parsing wdump output:")

	# Obtain wdump output
	output = []
	if (wdump_output == None):
		# Run wdump as subprocess, fetch output (NOTE: order of wdump arguments is important, '-a', '-Dx' won't work!)
		print_normal("Generating output for file '%s'..." % input_file)
		command = (wdump_exec, "-Dx", "-a", input_file)
		print_normal("Running command '%s'..." % str.join(" ", command))
		try:
			sub_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			return None
		if (sub_process.returncode != 0):
			print_error("Command failed with exit code %d:" % sub_process.returncode)
			print_error(sub_process.stdout if (sub_process.stdout != "") else "<no output>")
			return None
		output = sub_process.stdout.splitlines()
		print_normal("Writing plain output to file...")
		write_file(outfile_template, "wdump_output_plain.txt", output)
	else:
		# Read wdump output from file
		print_normal("Reading output from file '%s'..." % wdump_output)
		try:
			with open(wdump_output, "r") as file:
				output = file.read().splitlines()
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			return None

	# Read additional wdump output from file
	if (wdump_add_output != None):
		print_normal("Reading additional output from file '%s'..." % wdump_add_output)
		try:
			with open(wdump_add_output, "r") as file:
				output += file.read().splitlines()
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			return None

	# Process output, identify sections, distribute output to sections
	print_normal("Processing output (%d lines)..." % len(output))
	sections = OrderedDict()
	current_section = None
	for i in range(0, len(output)):

		# Fetch line, create stripped copy (leading + inner + trailing whitespace)
		line = output[i]
		line2 = str.join(" ", line.split())

		# Skip empty/whitespace-only lines
		if (line2 == ""):
			continue

		# Skip '[=]{78}' lines (see below)
		if (re.match("^[=]{78}$", line2)):
			continue

		# New section (lookahead one line; if next line is '[=]{78}', then current line is name of new section)
		if (i < len(output)-1 and re.match("^[=]{78}$", str.join(" ", output[i+1].split()))):
			name = line2
			name2 = name.lower()
			sections[name2] = OrderedDict([("name", name), ("data", [])])
			current_section = sections[name2]
			continue

		# Report stray lines
		if (current_section == None):
			print_warn("stray line: '%s'" % line)
			continue

		# Add original line to data of current section
		current_section["data"].append(line)

	# Print identified sections
	print_light("Identified sections:")
	for section in sections:
		print_normal(sections[section]["name"])

	# Decode section data
	print_light("Decoding section data...")
	for section in sections:
		print_normal("Section '%s'..." % sections[section]["name"])
		wdump_decode_data(sections[section])

	# Merge numbered sections, e.g. 'Module Info (section 0)' + 'Module Info (section 1)' -> sections["module info"]["data"] = OrderedDict([(0, <section 0>), (1, <section 1>)])
	# NOTE: using second variable here to avoid 'RuntimeError: OrderedDict mutated during iteration'; this is perfectly fine as we're only copying references around
	print_light("Merging numbered sections...")
	sections2 = OrderedDict()
	for section in sections:
		match = re.match("^(.+) \(section ([0-9]+)\)$", sections[section]["name"])
		if (match):
			name = match.group(1)
			name2 = name.lower()
			num = int(match.group(2))
			if (not name2 in sections2):
				sections2[name2] = OrderedDict([("name", name), ("data", OrderedDict())])
			sections2[name2]["data"][num] = sections[section]
			print_normal("Section '%s' -> '%s'..." % (sections[section]["name"], name))
		else:
			sections2[section] = sections[section]
	sections = sections2

	# Print final sections
	print_light("Final sections:")
	for section in sections:
		print_normal(sections[section]["name"])

	# Write parsed output to file
	print_light("Writing parsed output to file...")
	write_file(outfile_template, "wdump_output_parsed.txt", generate_pprint(sections))

	# Return results
	return sections



# ------------------------------------------------------------------------------
#                                                                              -
#  Fixup / Relocation                                                          -
#                                                                              -
# ------------------------------------------------------------------------------

# Get value of specified size from buffer
def fixup_get_value(buffer, offset, size, name=None, byteorder="little", signed=False):

	# Check bounds, raise exception if out of bounds
	# NOTE: we have to do this as slicing out of bounds will not raise exceptions; refer to:
	#       https://docs.python.org/3.6/library/stdtypes.html#sequence-types-list-tuple-range
	if (offset > len(buffer) or (offset + size) > len(buffer)):
		raise IndexError(name, size, len(buffer)-offset)

	# Convert bytes to value, advance offset
	value = int.from_bytes(buffer[offset:offset+size], byteorder=byteorder, signed=signed)
	offset += size

	# Return results
	return (value, offset)


# Get string of specified length from buffer
def fixup_get_string(buffer, offset, length, name=None, encoding="ascii"):

	# Check bounds, raise exception if out of bounds
	if (offset > len(buffer) or (offset + length) > len(buffer)):
		raise IndexError(name, length, len(buffer)-offset)

	# Decode string from bytes, advance offset
	string = bytes.decode(buffer[offset:offset+length], encoding=encoding)
	offset += length

	# Return results
	return (string, offset)


# Read and decode fixup / relocation data
# NOTE: we have to do this manually, i.e. by reading and decoding binary data directly from executable
#       as wdump does not provide all necessary information (mapping of fixup records to object pages)
# NOTE: based on document 'LX - Linear eXecutable Module Format Description - June 3, 1992'
#       [http://www.textfiles.com/programming/FORMATS/lxexe.txt]
#
# Fixup examples for MK1.EXE:
# ---------------------------
#
# Fixup record:
# 6535: <OrderedDict, 22 items>
#     'num':                        6535 (0x1987)
#     'page':                       30 (0x1e)
#     ...
#     'source object':              1 (0x1)
#     'source offset':              3511 (0xdb7)
#     'source offset 2':            122295 (0x1ddb7)
#     'target object':              2 (0x2)
#     'target offset':              150560 (0x24c20)
#
# Data in source object (in this case code):
# 1ddb6: b8 20 4c 02 00             mov    eax,0x24c20
#           ^ 0x1ddb7
#
# -> in object 1 (source object) at offset 0x1ddb7 (source offset), there is
#    a reference to object 2 (target object), offset 0x24c20 (target offset)
# -> when relocating, relocation offset for object 2 has to be added to value
#    0x24c20 stored at 0x1ddb7 in object 1
# -> e.g. object 2 relocation offset 0x12500:
#    0x24c20 + 0x12500 = 0x37120
#    1ddb6: b8 20 71 03 00          mov    eax,0x37120
# -> fixups work on binary data. Thus, it does not matter if source/target
#    objects carry code or data. In the example above, the fixup is applied
#    to code and the value to be 'fixed up' references data, but all other
#    combinations are possible as well, i.e. code-code, code-data, data-code,
#    data-data.
#
# Fixups at page boundaries:
# For fixups at page boundaries, there will always be two identical records,
# one for each side of the boundary (only source offset is different). Note
# the negative offsets (relative to page) on the second record of each pair:
# Page 25, record: 5371, source object: 1, source offset: 0xffe, source offset 2: 0x18ffe, target object: 2, target offset: 0x44480
# Page 26, record: 5793, source object: 1, source offset: 0x-2,  source offset 2: 0x18ffe, target object: 2, target offset: 0x44480
# Page 31, record: 6729, source object: 1, source offset: 0xffd, source offset 2: 0x1effd, target object: 2, target offset: 0x24b5c
# Page 32, record: 7008, source object: 1, source offset: 0x-3,  source offset 2: 0x1effd, target object: 2, target offset: 0x24b5c
# Page 40, record: 7399, source object: 1, source offset: 0xfff, source offset 2: 0x27fff, target object: 2, target offset: 0x5a874
# Page 41, record: 7879, source object: 1, source offset: 0x-1,  source offset 2: 0x27fff, target object: 2, target offset: 0x5a874
#
# -> for each pair, always record for page[i] + record for page[i+1]
# -> for each pair, always same distance of source offsets to boundary
#
def fixup_relocation_read_decode(wdump, input_file, outfile_template):

	# Sanity checks
	if (not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "file offset") or
	    not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "fixup section size") or
	    not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "offset of fixup page table") or
	    not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "offset of fixup record table") or
	    not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "offset of import module name table") or
	    not dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "offset of import procedure name table")):
		return None

	# Print header
	print_light("Reading and decoding fixup / relocation data:")
	fixup = OrderedDict()

	# Determine fixup tables offsets/sizes
	print_normal("Determining fixup tables offsets/sizes...")
	section = wdump["linear exe header (os/2 v2.x) - le"]["data"]
	fixup["offset page table"] = section["offset of fixup page table"]
	fixup["offset record table"] = section["offset of fixup record table"]
	fixup["offset module table"] = section["offset of import module name table"]
	fixup["offset procedure table"] = section["offset of import procedure name table"]
	fixup["file offset page table"] = section["file offset"] + section["offset of fixup page table"]
	fixup["file offset record table"] = section["file offset"] + section["offset of fixup record table"]
	fixup["file offset module table"] = section["file offset"] + section["offset of import module name table"]
	fixup["file offset procedure table"] = section["file offset"] + section["offset of import procedure name table"]
	fixup["size page table"] = section["offset of fixup record table"] - section["offset of fixup page table"]
	fixup["size record table"] = section["offset of import module name table"] - section["offset of fixup record table"]
	fixup["size module table"] = section["offset of import procedure name table"] - section["offset of import module name table"]
	fixup["size procedure table"] = section["offset of fixup page table"] + section["fixup section size"] - section["offset of import procedure name table"]
	fixup["size total"] = section["fixup section size"]

	# Read fixup data from input file
	fixup["data page table"] = b""
	fixup["data record table"] = b""
	fixup["data module table"] = b""
	fixup["data procedure table"] = b""
	fixup["data total"] = b""
	try:
		print_normal("Opening input file to read data...")
		with open(input_file, "rb") as infile:
			print_normal("Seeking to offset 0x%x..." % fixup["file offset page table"])
			infile.seek(fixup["file offset page table"])
			print_normal("Reading fixup data...")
			fixup["data total"] = infile.read(fixup["size total"])
			if (len(fixup["data total"]) != fixup["size total"]):
				print_warn("Fixup data length does not match size (expected %d bytes, got %d bytes)" % (fixup["size total"], len(fixup["data total"])))
	except Exception as exception:
		print_error("Error: %s" % str(exception))
		return None

	# Write fixup data to output file
	print_normal("Writing fixup data to file (%d bytes)..." % len(fixup["data total"]))
	write_file(outfile_template, "fixup_data.bin", fixup["data total"])

	# Slice fixup data into table data
	for table in ("page", "record", "module", "procedure"):
		fixup["data %s table" % table] = fixup["data total"][fixup["offset %s table" % table]-fixup["offset page table"]:fixup["offset %s table" % table]-fixup["offset page table"]+fixup["size %s table" % table]]
		if (len(fixup["data %s table" % table]) != fixup["size %s table" % table]):
			print_warn("%s table data length does not match size (expected %d bytes, got %d bytes)" % (table.capitalize(), fixup["size %s table" % table], len(fixup["data %s table" % table])))
	if (len(fixup["data page table"]) + len(fixup["data record table"]) + len(fixup["data module table"]) + len(fixup["data procedure table"]) != fixup["size total"]):
		print_warn("Sum of table data lengths does not match fixup data total size (expected %d bytes, got %d bytes)" % (fixup["size total"], len(fixup["data page table"]) + len(fixup["data record table"]) + len(fixup["data module table"]) + len(fixup["data procedure table"])))

	# Decode fixup page table data
	# NOTE: fixup page table is array of 32 bit values which specify offsets of fixup records data in fixup record table, e.g.
	#       0: 0x0, 1: 0x554, 2: 0x969, ... -> records for page 0 are stored in bytes 0x0..0x553 of record table data, entries
	#       for page 1 in bytes 0x554..0x968, ...
	# NOTE: by design, an additional entry (the last one) indicates end of fixup record table to facilitate offset calculation
	#       mechanism (see for-loop below)
	print_normal("Decoding fixup page table...")
	values = []
	offset = 0
	while (offset < len(fixup["data page table"])):
		try:
			(value, offset) = fixup_get_value(fixup["data page table"], offset, 4, "value")
			if (len(values) > 0 and value < values[-1]):
				print_warn("Current value %d (0x%x) is less than last value %d (0x%x), aborting decode" % (value, value, values[-1], values[-1]))
				break
			if (value > len(fixup["data record table"])):
				print_warn("Value %d (0x%x) is out of bounds, aborting decode" % (value, value))
				break
			values.append(value)
		except IndexError as error:
			print_warn("Failed to read next %s (need %d bytes, left %d bytes), aborting decode" % (error.args[0], error.args[1], error.args[2]))
			break

	# Construct fixup page table
	# NOTE: as page table data is array of 32 bit offset, we need value[i] & value[i+1] for calculation in each iteration
	fixup["page table"] = OrderedDict()
	page_num = 1
	for i in range(0, len(values)-1):
		fixup["page table"][page_num] = OrderedDict([("num", page_num), ("offset start", values[i]), ("offset end", values[i+1]), ("size", values[i+1]-values[i])])
		page_num += 1

	# Decode fixup record table data, construct fixup record table
	# NOTE: record table entries have variable sizes depending on certain bits in first two bytes of each entry
	print_normal("Decoding fixup record table...")
	fixup["record table"] = OrderedDict()
	record_num = 1
	for pte in fixup["page table"].values():

		# Slice record data for current page
		pte["data"] = fixup["data record table"][pte["offset start"]:pte["offset end"]]
		if (len(pte["data"]) != pte["size"]):
			print_warn("Page %d record data length does not match size (expected %d bytes, got %d bytes)" % (i, pte["size"], len(pte["data"])))

		# Decode record data for current page
		pte["records"] = OrderedDict()
		offset = 0
		while (offset < len(pte["data"])):
			try:
				# New record table entry
				rte = OrderedDict([("num", record_num), ("page", pte["num"]), ("offset start", offset), ("offset end", offset), ("size", 0)])

				# Read and decode flags bytes											# two bytes: one byte source flags, one byte target flags
				(rte["source flags"], offset) = fixup_get_value(pte["data"], offset, 1, "source flags")
				rte["source flags type"] = rte["source flags"] & 0x0f					# mask -> value 0x00..0x08
				rte["source flags alias"] = (rte["source flags"] >> 4) & 0x01			# flag -> if set, source refers to 16:16 alias
				rte["source flags list"] = (rte["source flags"] >> 5) & 0x01			# flag -> if set, source offset field is byte containing number of source offsets, list of source offsets follows end of record (after optional additive value)

				(rte["target flags"], offset) = fixup_get_value(pte["data"], offset, 1, "target flags")
				rte["target flags type"] = rte["target flags"] & 0x03					# mask -> value 0x00..0x03
				rte["target flags additive"] = (rte["target flags"] >> 2) & 0x01		# flag -> if set, additive value follows end of record (before optional source offset list)
				rte["target flags reserved"] = (rte["target flags"] >> 3) & 0x01		# flag -> must be zero
				rte["target flags offset type"] = (rte["target flags"] >> 4) & 0x01		# flag -> if set, target offset is 32 bits, otherwise 16 bits
				rte["target flags additive type"] = (rte["target flags"] >> 5) & 0x01	# flag -> if set, additive value is 32 bits, otherwise 16 bits
				rte["target flags obj/mod type"] = (rte["target flags"] >> 6) & 0x01	# flag -> if set, object number / module ordinal is 16 bits, otherwise 8 bits
				rte["target flags ordinal type"] = (rte["target flags"] >> 7) & 0x01	# flag -> if set, ordinal number is 8 bits, otherwise 16 bits

				# Add source object number
				rte["source object"] = None												# not part of record data, will be filled when processing objects/pages/segments below; initialized her for dict order

				# Read source offset field												# either byte containing number of source offset list entries or word containing source offset (NOTE: offset is signed!)
				if (rte["source flags list"] == 1):
					rte["source offset list"] = OrderedDict()							# will be filled after 'read target data'; initialized here for dict order
					rte["source offset list 2"] = OrderedDict()							# not part of record data, will be filled when processing objects/pages/segments below; initialized her for dict order
					(rte["source offset list length"], offset) = fixup_get_value(pte["data"], offset, 1, "source offset list length")
				else:
					(rte["source offset"], offset) = fixup_get_value(pte["data"], offset, 2, "source offset", signed=True)
					rte["source offset 2"] = None										# not part of record data, will be filled when processing objects/pages/segments below; initialized her for dict order

				# Read target data														# variable contents and sizes depending on target flags
				if (rte["target flags type"] == 0x00):									# 0x00h = Internal reference
					(rte["target object"], offset) = fixup_get_value(pte["data"], offset, 2, "target object") if (rte["target flags obj/mod type"] == 1) else fixup_get_value(pte["data"], offset, 1, "target object")
					if (rte["source flags type"] != 0x02):								# 0x02h = 16-bit selector fixup
						(rte["target offset"], offset) = fixup_get_value(pte["data"], offset, 4, "target offset") if (rte["target flags offset type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target offset")
				elif (rte["target flags type"] == 0x01):								# 01h = Imported reference by ordinal (NOTE: might be swapped with 0x02, documentation unclear on this)
					print_warn("First time target flags type %d (0x%x) is encountered, testing/debugging required" % (rte["target flags type"], rte["target flags type"]))
					(rte["target module ordinal"], offset) = fixup_get_value(pte["data"], offset, 2, "target module ordinal") if (rte["target flags obj/mod type"] == 1) else fixup_get_value(pte["data"], offset, 1, "target module ordinal")
					(rte["target procedure name offset"], offset) = fixup_get_value(pte["data"], offset, 4, "target procedure name offset") if (rte["target flags offset type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target procedure name offset")
					if (rte["target flags additive"] == 1):
						(rte["target additive value"], offset) = fixup_get_value(pte["data"], offset, 4, "target additive value") if (rte["target flags additive type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target additive value")
				elif (rte["target flags type"] == 0x02):								# 02h = Imported reference by name (NOTE: might be swapped with 0x01, documentation unclear on this)
					print_warn("First time target flags type %d (0x%x) is encountered, testing/debugging required" % (rte["target flags type"], rte["target flags type"]))
					(rte["target module ordinal"], offset) = fixup_get_value(pte["data"], offset, 2, "target module ordinal") if (rte["target flags obj/mod type"] == 1) else fixup_get_value(pte["data"], offset, 1, "target module ordinal")
					(rte["target import ordinal"], offset) = fixup_get_value(pte["data"], offset, 1, "target import ordinal") if (rte["target flags ordinal type"] == 1) else fixup_get_value(pte["data"], offset, 4, "target import ordinal") if (rte["target flags offset type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target import ordinal")
					if (rte["target flags additive"] == 1):
						(rte["target additive value"], offset) = fixup_get_value(pte["data"], offset, 4, "target additive value") if (rte["target flags additive type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target additive value")
				elif (rte["target flags type"] == 0x03):								# 03h = Internal reference via entry table
					print_warn("First time target flags type %d (0x%x) is encountered, testing/debugging required" % (rte["target flags type"], rte["target flags type"]))
					(rte["target entry ordinal"], offset) = fixup_get_value(pte["data"], offset, 2, "target entry ordinal") if (rte["target flags obj/mod type"] == 1) else fixup_get_value(pte["data"], offset, 1, "target entry ordinal")
					if (rte["target flags additive"] == 1):
						(rte["target additive value"], offset) = fixup_get_value(pte["data"], offset, 4, "target additive value") if (rte["target flags additive type"] == 1) else fixup_get_value(pte["data"], offset, 2, "target additive value")
				else:
					print_warn("Page %d, record %d: invalid target type: %d (0x%x), aborting decode" % (pte["num"], record_num, rte["target flags type"], rte["target flags type"]))
					break

				# Read source offset list												# list of words, only present if corresponding flag in source flags is set (NOTE: offsets are signed!)
				if (rte["source flags list"] == 1):
					rte["source offset list"] = OrderedDict()
					for i in range(1, rte["source offset list length"]+1):
						(rte["source offset list"][i], offset) = fixup_get_value(pte["data"], offset, 2, "source offset list entry %d" % i, signed=True)

				# Calculate end/size
				rte["offset end"] = offset
				rte["size"] = rte["offset end"] - rte["offset start"]

				# Store record table entry
				fixup["record table"][record_num] = rte
				pte["records"][record_num] = rte
				record_num += 1

			except IndexError as error:
				print_warn("Page %d, record %d: failed to read %s (need %d bytes, left %d bytes), aborting decode" % (pte["num"], record_num, error.args[0], error.args[1], error.args[2]))
				break

	# Process fixup records and calculate source offset(s) relative to parent object
	# NOTE: we do this because source offsets in fixup records are by design relative to their parent page, which is of no
	#       use to us in the further process
	# NOTE: pages are already numbered correctly in wdump data, e.g. object 1 has pages numbered 1..60, object 2 has pages
	#       numbered  61..130 -> page["num"] can be used
	print_normal("Calculating source offsets relative to parent object...")
	if (dict_path_exists(wdump, "object table", "data")):
		for object in wdump["object table"]["data"].values():
			if (not "pages" in object):
				print_warn("Object %d has no pages" % (object["num"]))
				continue
			object_offset = 0
			for page in object["pages"].values():
				if (dict_path_exists(fixup, "page table", page["num"], "records")):
					for rte in fixup["page table"][page["num"]]["records"].values():
						rte["source object"] = object["num"]
						if ("source offset" in rte):
							rte["source offset 2"] = rte["source offset"] + object_offset
						if ("source offset list" in rte):
							rte["source offset list 2"] = OrderedDict()
							for i in range(1, len(rte["source offset list"])+1):
								rte["source offset list 2"][i] = rte["source offset list"][i] + object_offset
				else:
					print_warn("Object %d page %d has no fixup records" % (object["num"], page["num"]))
				if (not "segments" in page):
					print_warn("Object %d page %d has no segments" % (object["num"], page["num"]))
					continue
				for segment in page["segments"].values():
					if (not "data" in segment):
						print_warn("Object %d page %d segment %d has no data" % (object["num"], page["num"], segment["num"]))
						continue
					object_offset += len(segment["data"])
	else:
		print_warn("Object table empty, skipping calculation")

	# Decode import module/procedure name table data (NOTE: needs testing/debugging, no real data to test with)
	for table in ("module", "procedure"):
		print_normal("Decoding import %s name table..." % table)
		fixup["%s table" % table] = OrderedDict()
		string_num = 1
		offset = 0
		while (offset < len(fixup["data %s table" % table])):
			try:
				(length, offset) = fixup_get_value(fixup["data %s table" % table], offset, 1, "string length")
				if (length == 0):
					print_warn("String %d is empty" % string_num)
				if (length > 127):
					print_warn("String %d is longer than 127 characters" % string_num)
				(string, offset) = fixup_get_string(fixup["data %s table" % table], offset, length, "string")
				fixup["%s table" % table][string_num] = string
				string_num += 1
			except IndexError as error:
				print_warn("Failed to read next %s (need %d bytes, left %d bytes), aborting decode" % (error.args[0], error.args[1], error.args[2]))
				break

	# Write results to file
	print_normal("Writing decoded data to file...")
	write_file(outfile_template, "fixup_data_decoded.txt", generate_pprint(fixup))

	# Return results
	return fixup



# ------------------------------------------------------------------------------
#                                                                              -
#  Disassembler                                                                -
#                                                                              -
# ------------------------------------------------------------------------------

# Splits assembler code line (objdump format)
# NOTE: handling of hex-only, comment, label, dots and empty lines was used before separating disassembly and disassembly structure; leaving this intact for future reference
def split_asm_line(line):

	# Normal asm line:
	#     9610:	b8 88 98 00 00       	mov    eax,0x9888
	# NOTE: regex: (.*?) non-greedy, (;.*)? capturing group + optional
	match = re.match("^([ ]*)([0-9a-fA-F]+):\t([0-9a-fA-F ]+)\t([^ ]+)[ ]*(.*?)\s*(;.*)?$", line)
	if (match):
		return { "type": "normal", "indent": match.group(1), "offset": int(match.group(2), 16), "hexdata": match.group(3).strip(), "command": match.group(4), "arguments": match.group(5), "comment": match.group(6) }

	# Hex-only line:
	#     963d:	c7 05 54 4b 02 00 07 	mov    DWORD PTR A9,0x7
	#     9644:	00 00 00
	# Second line is simply continuation of hex data of first line, i.e. mov above is 10 bytes long
	# NOTE: won't occur when running objdump with parameter '-w/--wide'
	#match = re.match("^([ ]*)([0-9a-fA-F]+):\t([0-9a-fA-F ]+?)\s*(;.*)?$", line)
	#if (match):
	#	return { "type": "hex", "indent": match.group(1), "offset": int(match.group(2), 16), "hexdata": match.group(3), "comment": match.group(4) }

	# Comment line:
	# ; some comment
	# NOTE: objdump should not contain comments
	#match = re.match("^(\s*)(;.*)$", line)
	#if (match):
	#	return { "type": "comment", "indent": match.group(1), "comment": match.group(2) }

	# Label line:
	# __8087cw:     ; size: WORD
	# NOTE: objdump should not contain labels
	#match = re.match("^([a-zA-Z0-9_]+):\s*(;.*)?$", line)
	#if (match):
	#	return { "type": "label", "label": match.group(1), "comment": match.group(2) }

	# Dots line:
	# ...
	# NOTE: placed by objdump for string of zeros; won't occur when running objdump with parameter '-z/--disassemble-zeroes'
	#if (line.strip() == "..."):
	#	return { "type": "dots" }

	# Empty line:
	# NOTE: objdump should not contain empty lines
	#if (line.strip() == ""):
	#	return { "type": "empty" }

	# Invalid line
	#print_error("Invalid assembler line: '%s'" % line)
	return None


# Checks if value (integer) is within ASCII range (https://www.asciitable.com/)
def is_ascii(value, only_printable=False):
	if (only_printable):
		if (value in (7, 8, 9, 10, 11, 12, 13, 27)) or (value in range(32, 127)):
			return True
	else:
		if (value in range(0, 128)):
			return True
	return False


# Generates define byte assembler line (objdump format)
def generate_define_byte(offset, value, comment=False):
	result = "%8x:\t%02x                   \t%-6s 0x%02x" % (offset, value, "db", value)
	if (comment == True):
		if (value == 0):
			char = "\\0"
		elif (value == 7):
			char = "\\a"
		elif (value == 8):
			char = "\\b"
		elif (value == 9):
			char = "\\t"
		elif (value == 10):
			char = "\\n"
		elif (value == 11):
			char = "\\v"
		elif (value == 12):
			char = "\\f"
		elif (value == 13):
			char = "\\r"
		elif (value == 27):
			char = "\\"
		elif (value >= 32 and value <= 126):
			char = chr(value)
		else:
			char = ""
		if (value > 0):
			result += "    ; dec: %3d, chr: '%s'" % (value, char)
	return result


# Inserts item into sorted structure; maintains sort order, returns inserted item
# Insertion modes:
# - 'default': inserts after existing items with equal offset
# - 'start':   inserts after existing items with equal offset, but before variables with equal offsets (for start items; see e.g. hint start for 'RAND' in object 2 of 'MK1_NO_DOS4GW.EXE')
# - 'end':     inserts before existing items with equal offset, starts looking for insertion point after start_item (for end items; see e.g. hint ends in object 2 of 'MK1_NO_DOS4GW.EXE')
# NOTE: item must have attribute 'offset', everything else is optional
def insert_structure_item(structure, item, mode="default", start_item=None):
	if (mode == "default"):
		for i in range(0, len(structure)):
			if (structure[i]["offset"] > item["offset"]):
				structure.insert(i, item)
				return structure[i]
	elif (mode == "start"):
		for i in range(0, len(structure)):
			if (structure[i]["offset"] > item["offset"]):
				while (i > 1 and structure[i-1]["offset"] == item["offset"] and structure[i-1]["type"] == "variable"):
					i -= 1
				structure.insert(i, item)
				return structure[i]
	elif (mode == "end"):
		for i in range(0, len(structure)):
			if (structure[i] == start_item):
				for j in range(i+1, len(structure)):
					if (structure[j]["offset"] >= item["offset"]):
						structure.insert(j, item)
						return structure[j]
	else:
		print_error("Unknown insertion mode '%s'" % mode)
		return None
	structure.append(item)
	return structure[-1]


# Determines and prints disassembly structure stats
def print_structure_stats(structure):
	stats = OrderedDict()
	for item in structure:
		key = "object" if item["type"].startswith("object") else "virtual padding" if item["type"].startswith("virtual padding") else "hint" if item["type"].startswith("hint") else "bad code" if item["type"].startswith("bad code") else item["type"] if item["type"] in ("module", "function", "branch", "variable") else "unknown"
		if (not key in stats):
			stats[key] = 0
		stats[key] += 1
	stats = [ "%s: %s" % (key, stats[key]) for key in stats.keys() ]
	print_normal("Structure: %s, total: %d" % (str.join(", ", stats), len(structure)))


# Generates a nice comment box; pre/post will be placed above/below box as-is; body will be placed inside box
def generate_comment_box(pre=[], body=[], post=[], width=80, autogrow=True, border="-"):
	if (isinstance(pre, str)):
		pre = pre.splitlines()
	if (isinstance(body, str)):
		body = body.splitlines()
	if (isinstance(post, str)):
		post = post.splitlines()

	if (autogrow == True):
		maxlen = 0
		for line in body:
			if (len(line) > maxlen):
				maxlen = len(line)
		if (maxlen > (width - 6)):
			width = maxlen + 6

	outer = ";" + border * (width - 1)
	inner = ";  %-" + str(width - 6) + "s  " + border

	result = []
	result += pre
	result.append(outer)
	for line in body:
		result.append(inner % line)
	result.append(outer)
	result += post
	return result


# Generates disassembly of data, i.e. assembler define lines
# Begins at offset, stops at end_offset = offset + length or when offset == data size; returns offset, actual length and disassembly lines
def generate_data_disassembly(data, size, offset, length, type):
	disassembly = []
	end_offset = offset + length
	actual_length = 0
	output_template = "%8x:\t%-20s \t%-6s %s"

	if (type == "auto"): 									# ASCII string auto-detection + bytes
		while (offset < size and offset < end_offset):
			if ((offset < size-4) and is_ascii(data[offset], only_printable=True) and is_ascii(data[offset+1], only_printable=True) and is_ascii(data[offset+2], only_printable=True) and is_ascii(data[offset+3], only_printable=True)):
				start_offset = offset
				is_string = True
				str_parts = []
				values = []
				while (offset < size and offset < end_offset):
					value = data[offset]
					values.append(value)
					if (value > 127):						# non-ASCII range
						is_string = False
						break
					elif (value >= 32 and value <= 126):	# ASCII printable range
						if (len(str_parts) == 0 or isinstance(str_parts[-1], int)):
							str_parts.append("")
						str_parts[-1] += chr(value)
					else:									# ASCII non-printable range
						str_parts.append(value)
					offset += 1
					if (value == 0):						# by doing it like this, last string does not have to be null-terminated
						break
				if (is_string == True):
					str_str = str.join(",", [ "0x%x" % part if isinstance(part, int) else "\"%s\"" % part for part in str_parts ])
					hex_str = str.join(" ", [ "%02x" % value for value in values ])
					disassembly.append(output_template % (start_offset, hex_str, "db", str_str))
					actual_length += len(values)
					continue
				offset = start_offset						# string turned out to be false positive; restore offset and continue normally
			disassembly.append(generate_define_byte(offset, data[offset], comment=True))
			actual_length += 1
			offset += 1

	elif (type == "strings"):								# null-terminated strings (may or may not be ASCII)
		while (offset < size and offset < end_offset):
			start_offset = offset
			str_parts = []
			values = []
			while (offset < size and offset < end_offset):
				value = data[offset]
				values.append(value)
				if (value >= 32 and value <= 126):			# ASCII printable range
					if (len(str_parts) == 0 or isinstance(str_parts[-1], int)):
						str_parts.append("")
					str_parts[-1] += chr(value)
				else:										# everything else
					str_parts.append(value)
				offset += 1
				if (value == 0):							# by doing it like this, last string does not have to be null-terminated
					break
			str_str = str.join(",", [ "0x%x" % part if isinstance(part, int) else "\"%s\"" % part for part in str_parts ])
			hex_str = str.join(" ", [ "%02x" % value for value in values ])
			disassembly.append(output_template % (start_offset, hex_str, "db", str_str))
			actual_length += len(values)

	elif (type == "string"):								# one single string (may or may not be ASCII/null-terminated)
		start_offset = offset
		str_parts = []
		values = []
		while (offset < size and offset < end_offset):
			value = data[offset]
			values.append(value)
			if (value >= 32 and value <= 126):				# ASCII printable range
				if (len(str_parts) == 0 or isinstance(str_parts[-1], int)):
					str_parts.append("")
				str_parts[-1] += chr(value)
			else:											# everything else
				str_parts.append(value)
			offset += 1
		str_str = str.join(",", [ "0x%x" % part if isinstance(part, int) else "\"%s\"" % part for part in str_parts ])
		hex_str = str.join(" ", [ "%02x" % value for value in values ])
		disassembly.append(output_template % (start_offset, hex_str, "db", str_str))
		actual_length += len(values)

	elif (type == "bytes"):									# bytes
		while (offset < size and offset < end_offset):
			disassembly.append(generate_define_byte(offset, data[offset], comment=True))
			actual_length += 1
			offset += 1

	# TODO: not sure if this works correctly for fwords as those are somewhat different (6 bytes, 4 bytes 32-bit offset + 2 bytes 16-bit selector);
	#       we have yet to see some FWORD in code to verify...
	elif (type in ("words", "dwords", "fwords", "qwords")):	# words, dwords, fwords, qwords
		type_defines = { "words": "dw", "dwords": "dd", "fwords": "df", "qwords": "dq" }
		type_sizes = { "words": 2, "dwords": 4, "fwords": 6, "qwords": 8 }
		type_define = type_defines[type]
		type_size = type_sizes[type]
		while (offset < size and offset < end_offset):
			if (offset < size - type_size and offset <= end_offset - type_size):
				values = list(data[offset:offset+type_size])
				hex_str = str.join(" ", [ "%02x" % value for value in values ])
				val_str = "0x" + str.join("", [ "%02x" % value for value in reversed(values) ])
				disassembly.append(output_template % (offset, hex_str, type_define, val_str))
				actual_length += type_size
				offset += type_size
			else:
				disassembly.append(generate_define_byte(offset, data[offset], comment=True))
				actual_length += 1
				offset += 1

	elif (type == "zeros"):									# zeros
		while (offset < size and data[offset] == 0):
			disassembly.append(generate_define_byte(offset, data[offset], comment=False))
			actual_length += 1
			offset += 1

	else:
		print_error("Unknown type '%s'" % type)

	return (offset, actual_length, disassembly)


# Disassembles code object
def disassemble_code_object(object, modules, globals, objdump_exec, data_object):
	print_light("Disassembling code object %d:" % object["num"])
	print_normal("Actual size: %d bytes, virtual size: %d bytes" % (object["size"], object["virtual memory size"]))
	disassembly = []
	structure = []
	insert_structure_item(structure, OrderedDict([("type", "object start"), ("offset", 0), ("name", "Object %d" % object["num"]), ("label", "object_%d" % object["num"]), ("objnum", object["num"])]))


	# ------------------------------------------------------------------------------
	#  former part of 'structure completion'                                       -
	# ------------------------------------------------------------------------------

	# Process modules, add them to structure
	print_normal("Adding modules to structure...")
	added = 0
	for module in modules:
		for offset in module["offsets"]:
			if (offset["segment"] == object["num"]):
				insert_structure_item(structure, OrderedDict([("type", "module"), ("offset", offset["offset"]), ("name", module["name"]), ("label", ntpath.basename(module["name"]).replace(".", "_").lower()), ("modnum", module["num"])]))
				added += 1
	print_normal("Added %d modules to structure" % added)

	# Process globals, add them to structure
	# TODO: can there be data globals (i.e. variables) in code objects?
	#print_normal("Adding globals to structure...")
	#added_functions = added_variables = added_total = 0
	#items = [ item for item in globals if (item["segment"] == object["num"]) ]
	#for item in items:
	#	if (item["type"] == "code"):
	#		insert_structure_item(structure, OrderedDict([("type", "function"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])]))
	#		added_functions += 1
	#	elif (item["type"] == "data"):
	#		#insert_structure_item(structure, OrderedDict([("type", "variable"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"]), ("sizes", item["sizes"] if "sizes" in item else [])]))
	#		insert_structure_item(structure, OrderedDict([("type", "variable"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])]))
	#		added_variables += 1
	#	added_total += 1
	#print_normal("Added %d globals to structure (%d functions, %d variables)" % (added_total, added_functions, added_variables))

	# Process globals of type 'code', add as functions to structure
	print_normal("Adding functions to structure...")
	added = 0
	items = [ item for item in globals if (item["segment"] == object["num"] and item["type"] == "code") ]
	for item in items:
		insert_structure_item(structure, OrderedDict([("type", "function"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])]))
		added += 1
	print_normal("Added %d functions to structure" % added)


	# ------------------------------------------------------------------------------
	#  initial disassembly                                                         -
	# ------------------------------------------------------------------------------

	# Write object data to temporary file for objdump (objdump can only read from files)
	print_normal("Writing object data to temporary file...")
	tmpfile = tempfile.NamedTemporaryFile(mode="w+b", delete=False)
	tmpfile.write(object["data"])
	tmpfile.close()

	# Disassembly loop (loops whenever bad code is detected)
	hint_index = 0
	bad_index = 0
	start_offset = 0
	while_again = True
	while (while_again == True):
		while_again = False

		# Run objdump, fetch output
		print_normal("Disassembling code from offset 0x%x to offset 0x%x..." % (start_offset, object["size"]-1))
		command = [objdump_exec, "--disassemble-all", "--disassemble-zeroes", "--wide", "--architecture=i386", "--disassembler-options=intel,i386", "--target=binary", "--start-address=0x%x" % start_offset, "--stop-address=0x%x" % (object["size"]-1), tmpfile.name]
		print_normal("Running command '%s'..." % str.join(" ", command))
		try:
			sub_process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True)
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			break
		if (sub_process.returncode != 0):
			print_error("Command failed with exit code %d:" % sub_process.returncode)
			print_error(sub_process.stdout if (sub_process.stdout != "") else "<no output>")
			break
		output = sub_process.stdout.splitlines()

		# Reduce output to actual code listing
		for i in range(0, len(output)):
			if (re.match("^([0-9a-fA-F]+) <.data(\+0x[0-9a-fA-F]+)?>:$", output[i])):
				output = output[i+1:]
				break

		# Process output, add to disassembly, detect bad code
		print_normal("Processing objdump output (%d lines)..." % len(output))
		for i in range(0, len(output)):
			line = output[i]
			disassembly.append(line)

			asm = split_asm_line(line)
			if (asm == None):
				print_warn("Invalid assembler line (line %d): %s" % (i+1, line))
				continue

			# Check for and report missed hints
			while (hint_index < len(object["hints"]) and object["hints"][hint_index]["offset"] < asm["offset"]):
				hint = object["hints"][hint_index]
				hint_index += 1
				print_error("Missed hint %d at offset 0x%x, size %d bytes, type '%s' (current offset 0x%x)" % (hint["num"], hint["offset"], hint["size"], hint["type"], asm["offset"]))

			# Check for and process hint for current offset
			if (hint_index < len(object["hints"]) and object["hints"][hint_index]["offset"] == asm["offset"]):
				del disassembly[-1] # remove last line of disassembly (was added at start of for loop)
				hint = object["hints"][hint_index]
				hint_index += 1
				print_warn("Hint %d at offset 0x%x, size %d bytes, type '%s'" % (hint["num"], hint["offset"], hint["size"], hint["type"]), end="")
				item = insert_structure_item(structure, OrderedDict([("type", "hint start"), ("offset", hint["offset"]), ("name", "Hint %d" % hint["num"]), ("label", "hint_%d" % hint["num"]), ("hintnum", hint["num"]), ("size", hint["size"]), ("subtype", hint["type"])]), mode="start")
				if (hint["type"] == "data"):
					print_warn(", subtype '%s', comment '%s'" % (hint["subtype"], hint["comment"] if ("comment" in hint) else "<none>"))
					item.update([("subtype2", hint["subtype"])] + ([("comment", hint["comment"])] if ("comment" in hint) else []))
					(start_offset, item["size"], data_disassembly) = generate_data_disassembly(object["data"], object["size"], hint["offset"], hint["size"], hint["subtype"])
					disassembly += data_disassembly
				insert_structure_item(structure, OrderedDict([("type", "hint end"), ("offset", start_offset), ("name", "Hint %d" % hint["num"]), ("label", "hint_%d" % hint["num"])]), mode="end", start_item=item)
				if (start_offset < object["size"]):
					print_warn("Continuing disassembly at offset 0x%x..." % start_offset)
					while_again = True
				else:
					print_warn("Reached end of object data at offset 0x%x." % start_offset)
				break # break for-loop -> next iteration of 'while (while_again == True)' loop

			# Detect bad code: if ret or jmp is followed by zero(s), find first non-zero byte after
			# command and continue disassembling from that point on; add zero(s) back as padding data
			# NOTE: this variant relies on 'objdump --wide'; for other variants, see 'archive/code_snippets_bad_code_detection.py'
			if (asm["type"] == "normal" and (asm["command"] == "ret" or asm["command"] == "jmp")):
				offset = asm["offset"] + len(asm["hexdata"].strip().split())
				if (offset < object["size"] and object["data"][offset] == 0):
					bad_index += 1
					bad_offset = offset
					bad_type = "zero after ret" if (asm["command"] == "ret") else "zero after jmp" if (asm["command"] == "jmp") else "unknown"
					print_warn("Bad code %d at offset 0x%x, type '%s':" % (bad_index, bad_offset, bad_type))
					context = [output[i], output[i+1], output[i+2]] if (i < len(output)-2) else [output[i], output[i+1]] if (i < len(output)-1) else [output[i]]
					for j in range(0, len(context)):
						print_warn("line %d: %s" % (len(disassembly)+j, context[j]))
					item = insert_structure_item(structure, OrderedDict([("type", "bad code start"), ("offset", bad_offset), ("name", "Bad code %d" % bad_index), ("label", "bad_code_%d" % bad_index), ("context", context), ("padding", 0), ("subtype", bad_type)]), mode="start")
					(start_offset, item["padding"], data_disassembly) = generate_data_disassembly(object["data"], object["size"], bad_offset, 0, "zeros")
					disassembly += data_disassembly
					insert_structure_item(structure, OrderedDict([("type", "bad code end"), ("offset", start_offset), ("name", "Bad code %d" % bad_index), ("label", "bad_code_%d" % bad_index)]), mode="end", start_item=item)
					if (start_offset < object["size"]):
						print_warn("Continuing disassembly at offset 0x%x..." % start_offset)
						while_again = True
					else:
						print_warn("Reached end of object data at offset 0x%x." % start_offset)
					break # break for-loop -> go to start of while-loop

	# Remove temporary file
	print_normal("Removing temporary file...")
	os.remove(tmpfile.name)

	# If object's actual size < virtual size, append padding data
	if (object["size"] < object["virtual memory size"]):
		print_normal("Appending virtual size padding data (%d bytes)..." % (object["virtual memory size"] - object["size"]))
		insert_structure_item(structure, OrderedDict([("type", "virtual padding start"), ("offset", object["size"]), ("name", "Virtual padding"), ("label", "virtual_padding"), ("size", object["virtual memory size"] - object["size"]), ("objnum", object["num"])]))
		for offset in range(object["size"], object["virtual memory size"]):
			disassembly.append(generate_define_byte(offset, 0, comment=True if (object["type"] == "data") else False))
		insert_structure_item(structure, OrderedDict([("type", "virtual padding end"), ("offset", object["virtual memory size"]), ("name", "Virtual padding"), ("label", "virtual_padding")]))

	# Append object end to structure
	insert_structure_item(structure, OrderedDict([("type", "object end"), ("offset", object["virtual memory size"] if (object["virtual memory size"] > object["size"]) else object["size"]), ("name", "Object %d" % object["num"]), ("label", "object_%d" % object["num"]), ("objnum", object["num"])]))


	# ------------------------------------------------------------------------------
	#  branch analysis (call/jump commands)                                        -
	# ------------------------------------------------------------------------------

	# Analyze branches (i.e. target addresses of call/jump instructions), add them to structure
	print_normal("Analyzing branches...")

	# Collect already known addresses, i.e. structure items of type 'function'
	#known_addresses = OrderedDict()
	#for item in structure:
	#	#if (not item["type"] in ("object start", "module", "function")):
	#	if (item["type"] != "function"):
	#		continue
	#	if (not item["offset"] in known_addresses):
	#		known_addresses[item["offset"]] = []
	#	known_addresses[item["offset"]].append(item)

	# Collect already known addresses, i.e. globals of type 'code' belonging to current object
	known_addresses = OrderedDict()
	for item in globals:
		if (item["segment"] != object["num"] or item["type"] != "code"):
			continue
		if (not item["offset"] in known_addresses):
			known_addresses[item["offset"]] = []
		known_addresses[item["offset"]].append(item)
	print_normal("Known addresses: %d" % len(known_addresses))

	# Perform analysis
	added = 0
	for i in range(0, len(disassembly)):
		line = disassembly[i]
		asm = split_asm_line(line)
		if (asm == None):
			print_warn("Invalid assembler line (line %d): %s" % (i+1, line))
			continue

		if (asm["type"] == "normal" and (asm["command"] == "call" or asm["command"].startswith("j"))):
			match = re.match("^0x([0-9a-fA-F]+)$", asm["arguments"].strip())
			if (match == None):
				#print_warn("Failed to match address (line %d): %s" % (i+1, line))
				continue
			address = int(match.group(1), 16)

			if (address in known_addresses):
				#names = [ "'%s'" % item["name"] if ("name" in item) else "'<none'>" for item in known_addresses[address] ]
				#print_normal("Known item(s) %s for address 0x%x" % (str.join(", ", names), address))
				continue

			#print_normal("Adding branch for address 0x%x" % address)
			item = insert_structure_item(structure, OrderedDict([("type", "branch"), ("offset", address), ("name", None), ("label", None)]))
			known_addresses[address] = [ item ]
			added += 1

	# Print results
	print_normal("Added %d branches to structure" % added)

	# Process structure, name branches
	# NOTE: structure has to be sorted for this to work correctly!
	print_normal("Naming branches...")
	parent = None
	pnums = {}
	named = 0
	for i in range(0, len(structure)):
		item = structure[i]
		if (item["type"] in ("object start", "module", "function")):
			parent = item
			if (not parent["name"] in pnums):
				pnums[parent["name"]] = 0
		if (item["type"] == "branch"):
			if (parent != None):
				pnums[parent["name"]] += 1
				item["name"] = "%s branch %d" % (parent["name"], pnums[parent["name"]])
				item["label"] = "%s_branch_%d" % (parent["label"], pnums[parent["name"]])
				named += 1
			else:
				print_error("[should-never-occur] Branch without parent")

	print_normal("Named %d branches" % named)


	# ------------------------------------------------------------------------------
	#  code segment reference ('cs:0x...') analysis                                -
	# ------------------------------------------------------------------------------

	# Analyze code segment references (i.e. 'cs:0x...' occurences in code), determine access size, add missing references to globals
	# NOTE: this modifies globals, not structure!
	print_normal("Analyzing code segment references...")

	# Collect already known addresses, i.e. globals of type 'data' belonging to current object
	known_addresses = OrderedDict()
	for item in globals:
		#if (item["segment"] != object["num"] or item["type"] != "data"):
		if (item["segment"] != object["num"]): # also gather 'code' items, e.g. '_Alphabet'
			continue
		if (not item["offset"] in known_addresses):
			known_addresses[item["offset"]] = []
		known_addresses[item["offset"]].append(item)
	print_normal("Known addresses: %d" % len(known_addresses))

	# Perform analysis
	added = 0
	for i in range(0, len(disassembly)):
		line = disassembly[i]
		asm = split_asm_line(line)
		if (asm == None):
			print_warn("Invalid assembler line (line %d): %s" % (i+1, line))
			continue

		if (asm["type"] == "normal"):
			match = re.search("cs:0x([0-9a-fA-F]+)", asm["arguments"])
			if (match == None):
				match = re.search("cs:\[.+[+-]0x([0-9a-fA-F]+)\]", asm["arguments"])
			if (match == None):
				continue
			addr_str = match.group(0)
			addr_val = int(match.group(1), 16)

			# Determine access size
			access_size = None
			match = re.search("([a-zA-Z]+) PTR %s" % re.escape(addr_str), asm["arguments"])
			if (match):
				access_size = match.group(1)
			if (access_size == None):
				if (asm["command"] == "mov"):
					# NOTE: order is important! longest matches first, e.g. try matching 'eax' before 'ax'!
					if (re.search("(eax|ebx|ecx|edx),%s" % addr_str, asm["arguments"])):
						access_size = "DWORD"
					elif (re.search("%s,(eax|ebx|ecx|edx)" % addr_str, asm["arguments"])):
						access_size = "DWORD"
					elif (re.search("(ax|bx|cx|dx),%s" % addr_str, asm["arguments"])):
						access_size = "WORD"
					elif (re.search("%s,(ax|bx|cx|dx)" % addr_str, asm["arguments"])):
						access_size = "WORD"
					elif (re.search("(al|ah|bl|bh|cl|ch|dl|dh),%s" % addr_str, asm["arguments"])):
						access_size = "BYTE"
					elif (re.search("%s,(al|ah|bl|bh|cl|ch|dl|dh)" % addr_str, asm["arguments"])):
						access_size = "BYTE"
			if (access_size == None):
				print_warn("Failed to determine cs access size (line %d): %s" % (i+1, line))

			# Check if address is known; if so, add access size if available
			if (addr_val in known_addresses):
				#names = [ "'%s'" % item["name"] if ("name" in item) else "'<none'>" for item in known_addresses[address] ]
				#print_normal("Known item(s) %s for address 0x%x" % (str.join(", ", names), address))
				if (access_size != None):
					for item in known_addresses[addr_val]:
						if (not "sizes" in item):
							item["sizes"] = []
						if (not access_size in item["sizes"]):
							item["sizes"].append(access_size)
				continue

			# TESTING DEBUG report lines containing 'ds:' (should not occur)
			if ("ds:" in line):
				print_error("[should-never-occur] Line contains 'ds:': (line %d): %s" % (i+1, line))

			# Add new global
			#print_normal("Adding global for code segment reference cs:0x%x" % addr_val)
			globals.append(OrderedDict([("name", None), ("module", None), ("segment", object["num"]), ("offset", addr_val), ("type", "data")] + ([("sizes", [ access_size ])] if (access_size != None) else [])))
			known_addresses[addr_val] = [ globals[-1] ]

			# Add new structure item (partial code segment variable)
			#print_normal("Adding structure item for code segment reference cs:0x%x" % addr_val)
			item = globals[-1]
			insert_structure_item(structure, OrderedDict([("type", "partial-cs-var"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])] + ([("sizes", item["sizes"])] if "sizes" in item else []) + [("global", item)]))

			added += 1

	# Sort globals
	globals.sort(key=lambda item: (item["segment"], item["offset"]))

	# Print results
	print_normal("Added %d globals for code segment references" % added)
	print_normal("Added %d structure items for code segment references" % added)

	# Process structure, complete partial code segment variables (i.e. fill in all missing information)
	# NOTE: structure has to be sorted for this to work correctly!
	# NOTE: link to global is used to fill in missing information for global as well; link is removed once this is done
	print_normal("Completing partial code segment variables...")
	parent = None
	pnums = {}
	last_modnum = None
	completed = 0
	for i in range(0, len(structure)):
		item = structure[i]
		# TODO: use last variable as parent if current variable is within size of last variable, e.g.
		# A2:                                                ; sizes: DWORD, WORD, BYTE
		#    24b40:	00                   	db     0x00
		#    24b41:	00                   	db     0x00
		# A2_variable_1:                                     ; size: WORD
		#    24b42:	00                   	db     0x00
		#    24b43:	00                   	db     0x00
		#if (item["type"] in ("object start", "module", "variable")): # using variables as parent is sometimes helpful (e.g. module 'RAM.ASM'), but not always
		if (item["type"] in ("object start", "module")):
			parent = item
			if (not parent["name"] in pnums):
				pnums[parent["name"]] = 0
			if (item["type"] == "module"):
				last_modnum = item["modnum"]
		if (item["type"] == "partial-cs-var"):
			if (parent != None):
				pnums[parent["name"]] += 1
				item["type"] = "variable"
				item["name"] = "%s variable %d" % (parent["name"], pnums[parent["name"]])
				item["label"] = "%s_variable_%d" % (parent["label"], pnums[parent["name"]])
				item["global"]["name"] = item["label"]
				item["global"]["module"] = last_modnum
				#item["global"]["segment"] = object["num"]
				del(item["global"])
				completed += 1
			else:
				print_error("[should-never-occur] Partial code segment variable without parent")

	print_normal("Completed %d partial code segment variables" % completed)


	# ------------------------------------------------------------------------------
	#  data segment reference ('ds:0x...') analysis                                -
	# ------------------------------------------------------------------------------

	# We can only do this if we have a designated data object (without, we have no way of knowing which object 'ds:...' references point to)
	if (data_object != None):

		# Analyze data segment references (i.e. 'ds:0x...' occurences in code), determine access size, add missing references to globals
		# NOTE: this modifies globals, not structure!
		# NOTE: added globals will be picked up by automatic data object during its disassembly
		# NOTE: globals may not be sorted after this until 'segment' is filled in (because 'None' is not sortable)
		print_normal("Analyzing data segment references...")

		# Collect already known addresses, i.e. globals of type 'data' belonging to data object
		known_addresses = OrderedDict()
		for item in globals:
			if (item["segment"] != data_object or item["type"] != "data"):
				continue
			if (not item["offset"] in known_addresses):
				known_addresses[item["offset"]] = []
			known_addresses[item["offset"]].append(item)
		print_normal("Known addresses: %d" % len(known_addresses))

		# Perform analysis
		added = 0
		for i in range(0, len(disassembly)):
			line = disassembly[i]
			asm = split_asm_line(line)
			if (asm == None):
				print_warn("Invalid assembler line (line %d): %s" % (i+1, line))
				continue

			if (asm["type"] == "normal"):
				match = re.search("ds:0x([0-9a-fA-F]+)", asm["arguments"])
				if (match == None):
					match = re.search("ds:\[.+[+-]0x([0-9a-fA-F]+)\]", asm["arguments"])
				#if (match == None): # TODO: try re-enabling this once relocation + fixup is in place; without, this gives way to many false-positives
				#	match = re.search("(?<!s:)\[.+[+-]0x([0-9a-fA-F]+)\]", asm["arguments"]) # (?<!s:) -> negative lookahead -> may not preceded by 's:' -> https://stackoverflow.com/a/47886935
				if (match == None):
					continue
				addr_str = match.group(0)
				addr_val = int(match.group(1), 16)

				# TESTING MK1.EXE hard-code to avoid problems resulting from third regex above
				# TODO: we need to evolve this into something dynamic -> perhaps check if reference points to data belonging to same module?
				#       problem is there's no way to tell if offset is just a number or a data reference
				#       -> solution to this should be relocation + fixups
				#if (addr_val < 0x6f4):
				#	continue

				# Determine access size
				access_size = None
				match = re.search("([a-zA-Z]+) PTR %s" % re.escape(addr_str), asm["arguments"])
				if (match):
					access_size = match.group(1)
				if (access_size == None):
					if (asm["command"] == "mov"):
						# NOTE: order is important! longest matches first, e.g. try matching 'eax' before 'ax'!
						if (re.search("(eax|ebx|ecx|edx),%s" % addr_str, asm["arguments"])):
							access_size = "DWORD"
						elif (re.search("%s,(eax|ebx|ecx|edx)" % addr_str, asm["arguments"])):
							access_size = "DWORD"
						elif (re.search("(ax|bx|cx|dx),%s" % addr_str, asm["arguments"])):
							access_size = "WORD"
						elif (re.search("%s,(ax|bx|cx|dx)" % addr_str, asm["arguments"])):
							access_size = "WORD"
						elif (re.search("(al|ah|bl|bh|cl|ch|dl|dh),%s" % addr_str, asm["arguments"])):
							access_size = "BYTE"
						elif (re.search("%s,(al|ah|bl|bh|cl|ch|dl|dh)" % addr_str, asm["arguments"])):
							access_size = "BYTE"
				if (access_size == None):
					print_warn("Failed to determine ds access size (line %d): %s" % (i+1, line))

				# Check if address is known; if so, add access size if available
				if (addr_val in known_addresses):
					#names = [ "'%s'" % item["name"] if ("name" in item) else "'<none'>" for item in known_addresses[address] ]
					#print_normal("Known item(s) %s for address 0x%x" % (str.join(", ", names), address))
					if (access_size != None):
						for item in known_addresses[addr_val]:
							if (not "sizes" in item):
								item["sizes"] = []
							if (not access_size in item["sizes"]):
								item["sizes"].append(access_size)
					continue

				# TESTING DEBUG report lines containing 'cs:' (should not occur)
				if ("cs:" in line):
					print_error("[should-never-occur] Line contains 'cs:': (line %d): %s" % (i+1, line))

				# Add new global
				#print_normal("Adding global for data segment reference ds:0x%x" % addr_val)
				globals.append(OrderedDict([("name", None), ("module", None), ("segment", None), ("offset", addr_val), ("type", "data")] + ([("sizes", [ access_size ])] if (access_size != None) else [])))
				known_addresses[addr_val] = [ globals[-1] ]
				added += 1

		print_normal("Added %d globals for data segment references" % added)

	else:
		print_warn("No data object specified, skipping data segment reference analysis.")


	# ------------------------------------------------------------------------------
	#  done                                                                        -
	# ------------------------------------------------------------------------------

	# Print stats, store results
	print_normal("Disassembly: %d lines, %d bytes" % (len(disassembly), len(str.join(os.linesep, disassembly))))
	print_structure_stats(structure)
	object["disassembly1"] = disassembly
	object["structure"] = structure


# Disassembles data object
def disassemble_data_object(object, modules, globals, data_object):
	print_light("Disassembling data object %d:" % object["num"])
	print_normal("Actual size: %d bytes, virtual size: %d bytes" % (object["size"], object["virtual memory size"]))
	disassembly = []
	structure = []
	insert_structure_item(structure, OrderedDict([("type", "object start"), ("offset", 0), ("name", "Object %d" % object["num"]), ("label", "object_%d" % object["num"]), ("objnum", object["num"])]))

	# Process modules, add them to structure
	print_normal("Adding modules to structure...")
	added = 0
	for module in modules:
		for offset in module["offsets"]:
			if (offset["segment"] == object["num"]):
				insert_structure_item(structure, OrderedDict([("type", "module"), ("offset", offset["offset"]), ("name", module["name"]), ("label", ntpath.basename(module["name"]).replace(".", "_").lower()), ("modnum", module["num"])]))
				added += 1
	print_normal("Added %d modules to structure" % added)

	# Process globals, add them to structure
	# TODO: can there be code globals (i.e. functions) in data objects?
	#print_normal("Adding globals to structure...")
	#added_functions = added_variables = added_total = 0
	#items = [ item for item in globals if (item["segment"] == object["num"]) ]
	#for item in items:
	#	if (item["type"] == "code"):
	#		insert_structure_item(structure, OrderedDict([("type", "function"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])]))
	#		added_functions += 1
	#	elif (item["type"] == "data"):
	#		insert_structure_item(structure, OrderedDict([("type", "variable"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"]), ("sizes", item["sizes"] if "sizes" in item else [])]))
	#		added_variables += 1
	#	added_total += 1
	#print_normal("Added %d globals to structure (%d functions, %d variables)" % (added_total, added_functions, added_variables))

	# Process globals of type 'data', add as variables to structure
	print_normal("Adding variables to structure...")
	added = 0
	items = [ item for item in globals if (item["segment"] == object["num"] and item["type"] == "data") ]
	for item in items:
		insert_structure_item(structure, OrderedDict([("type", "variable"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])] + ([("sizes", item["sizes"])] if "sizes" in item else [])))
		added += 1
	print_normal("Added %d variables to structure" % added)

	# Special handling if object is designated data object
	if (object["num"] == data_object):

		# Process globals of type 'data' with segment 'None' (i.e. unassigned variables), add as partial data segment variables to structure
		# NOTE: these globals come from data segment reference ('ds:0x...') analysis of code objects
		# NOTE: link to global is temporarily required for assignment below, will be removed later; could also use map structure -> item
		print_normal("Adding unassigned variables to structure...")
		added = 0
		items = [ item for item in globals if (item["segment"] == None and item["type"] == "data") ]
		for item in items:
			insert_structure_item(structure, OrderedDict([("type", "partial-ds-var"), ("offset", item["offset"]), ("name", item["name"]), ("label", item["name"])] + ([("sizes", item["sizes"])] if "sizes" in item else []) + [("global", item)]))
			added += 1
		print_normal("Added %d unassigned variables to structure" % added)

		# Process structure, complete partial data segment variables (i.e. fill in all missing information)
		# NOTE: structure has to be sorted for this to work correctly!
		# NOTE: link to global is used to fill in missing information for global as well; link is removed once this is done
		print_normal("Completing partial data segment variables...")
		parent = None
		pnums = {}
		last_modnum = None
		completed = 0
		for i in range(0, len(structure)):
			item = structure[i]
			# TODO: use last variable as parent if current variable is within size of last variable -> see example in comment on 'cs:...' analysis
			#if (item["type"] in ("object start", "module", "variable")): # using variables as parent is sometimes helpful (e.g. module 'RAM.ASM'), but not always
			if (item["type"] in ("object start", "module")):
				parent = item
				if (not parent["name"] in pnums):
					pnums[parent["name"]] = 0
				if (item["type"] == "module"):
					last_modnum = item["modnum"]
			if (item["type"] == "partial-ds-var"):
				if (parent != None):
					pnums[parent["name"]] += 1
					item["type"] = "variable"
					item["name"] = "%s variable %d" % (parent["name"], pnums[parent["name"]])
					item["label"] = "%s_variable_%d" % (parent["label"], pnums[parent["name"]])
					item["global"]["name"] = item["label"]
					item["global"]["module"] = last_modnum
					item["global"]["segment"] = object["num"]
					del(item["global"])
					completed += 1
				else:
					print_error("[should-never-occur] Partial data segment variable without parent")

		print_normal("Completed %d partial data segment variables" % completed)

		# Globals can now be safely sorted as there should be no missing information left at this point (i.e. no 'None')
		globals.sort(key=lambda item: (item["segment"], item["offset"]))

	# TESTING Add virtual padding data to object data now so it is processed like normal data (important for hints, variables etc.)
	if (object["size"] < object["virtual memory size"]):
		print_normal("Appending virtual size padding data (%d bytes)..." % (object["virtual memory size"] - object["size"]))
		insert_structure_item(structure, OrderedDict([("type", "virtual padding start"), ("offset", object["size"]), ("name", "Virtual padding"), ("label", "virtual_padding"), ("size", object["virtual memory size"] - object["size"]), ("objnum", object["num"])]))
		insert_structure_item(structure, OrderedDict([("type", "virtual padding end"), ("offset", object["virtual memory size"]), ("name", "Virtual padding"), ("label", "virtual_padding")]))
		object["data"] += bytes(object["virtual memory size"] - object["size"])
		object["size"] = len(object["data"])

	# Disassemble object data
	print_normal("Disassembling data from offset 0x%x to offset 0x%x..." % (0, object["size"]-1))
	hint_index = 0
	struct_index = 0
	offset = 0
	type_to_size = { "qwords": 8, "fwords": 6, "dwords": 4, "words": 2, "bytes": 1 }
	size_to_type = { 8: "qwords", 6: "fwords", 4: "dwords", 2: "words", 1: "bytes" }
	while (offset < object["size"]):

		# Check for and report missed hints
		while (hint_index < len(object["hints"]) and object["hints"][hint_index]["offset"] < offset):
			hint = object["hints"][hint_index]
			hint_index += 1
			print_error("Missed hint %d at offset 0x%x, size %d bytes, type '%s' (current offset 0x%x)" % (hint["num"], hint["offset"], hint["size"], hint["type"], offset))

		# Check for and process hint for current offset
		if (hint_index < len(object["hints"]) and object["hints"][hint_index]["offset"] == offset):
			hint = object["hints"][hint_index]
			hint_index += 1
			print_warn("Hint %d at offset 0x%x, size %d bytes, type '%s'" % (hint["num"], hint["offset"], hint["size"], hint["type"]), end="")
			item = insert_structure_item(structure, OrderedDict([("type", "hint start"), ("offset", hint["offset"]), ("name", "Hint %d" % hint["num"]), ("label", "hint_%d" % hint["num"]), ("hintnum", hint["num"]), ("size", hint["size"]), ("subtype", hint["type"])]), mode="start")
			if (hint["type"] == "data"):
				print_warn(", subtype '%s', comment '%s'" % (hint["subtype"], hint["comment"] if ("comment" in hint) else "<none>"))
				item.update([("subtype2", hint["subtype"])] + ([("comment", hint["comment"])] if ("comment" in hint) else []))
				(offset, item["size"], data_disassembly) = generate_data_disassembly(object["data"], object["size"], hint["offset"], hint["size"], hint["subtype"])
				disassembly += data_disassembly
			insert_structure_item(structure, OrderedDict([("type", "hint end"), ("offset", offset), ("name", "Hint %d" % hint["num"]), ("label", "hint_%d" % hint["num"])]), mode="end", start_item=item)
			#while (struct_index < len(structure) and structure[struct_index]["offset"] <= offset): # skip structure items that lie within hint range; we ignore those as hint takes precedence
			while (struct_index < len(structure) and structure[struct_index]["offset"] < offset): # skip structure items that lie within hint range; we ignore those as hint takes precedence
				item = structure[struct_index]
				struct_index += 1
				#print_normal("Skipping structure item '%s', type '%s' at offset 0x%x (current offset 0x%x)" % (item["name"], item["type"], item["offset"], offset))
			continue # next iteration 'while (offset < object["size"])' loop

		# Check for and report missed structure items
		while (struct_index < len(structure) and structure[struct_index]["offset"] < offset):
			item = structure[struct_index]
			struct_index += 1
			print_warn("Missed structure item '%s', type '%s' at offset 0x%x (current offset 0x%x)" % (item["name"], item["type"], item["offset"], offset))

		# Process structure item for current offset
		# TODO: shouldn't this be a while loop due to the continues? -> yes, but last continue poses a problem as that one needs to continue outer while-loop
		if (struct_index < len(structure) and structure[struct_index]["offset"] == offset):
			item = structure[struct_index]
			struct_index += 1
			if (item["type"] != "variable"):
				continue
			if (not "sizes" in item):
				continue

			# Determine data type/size (choose highest if multiple sizes)
			if ("QWORD" in item["sizes"]):
				data_type = "qwords"
			elif ("FWORD" in item["sizes"]):
				data_type = "fwords"
			elif ("DWORD" in item["sizes"]):
				data_type = "dwords"
			elif ("WORD" in item["sizes"]):
				data_type = "words"
			elif ("BYTE" in item["sizes"]):
				data_type = "bytes"
			else:
				print_error("[should-never-occur] Unable to determine data type/size: %s" % str.join(", ", item["sizes"]))
				data_type = "bytes"
			data_size = type_to_size[data_type]

			# Skip structure items with same offset (note '==' here!)
			while (struct_index < len(structure) and structure[struct_index]["offset"] == offset):
				item = structure[struct_index]
				struct_index += 1
				#print_normal("Skipping structure item '%s' (type '%s') at offset 0x%x; current offset 0x%x" % (item["name"], item["type"], item["offset"], offset))

			# Check if data size would overlap with / obstruct next structure item; if so, use
			# distance to next structure item as basis and determine nearest smaller data size
			if (struct_index < len(structure) and structure[struct_index]["offset"] < offset + data_size):
				data_size = structure[struct_index]["offset"] - offset
				if (data_size > 0):
					while (data_size > 1 and not data_size in size_to_type):
						data_size -= 1
					data_type = size_to_type[data_size]
				else:
					print_error("[should-never-occur] Something is seriously wrong with data size: %d" % data_size)
					data_type = "bytes"
					data_size = type_to_size[data_type]

			# Disassemble data based on determined type/size
			(offset, _, data_disassembly) = generate_data_disassembly(object["data"], object["size"], offset, data_size, data_type) # https://www.pythonmania.net/en/2017/03/05/underscore-in-python/
			disassembly += data_disassembly
			continue

		# Disassemble one byte, advance offset
		value = object["data"][offset]
		disassembly.append(generate_define_byte(offset, value, comment=True))
		offset += 1

	# If object's actual size < virtual size, append padding data
	#if (object["size"] < object["virtual memory size"]):
	#	print_normal("Appending virtual size padding data (%d bytes)..." % (object["virtual memory size"] - object["size"]))
	#	insert_structure_item(structure, OrderedDict([("type", "virtual padding start"), ("offset", object["size"]), ("name", "Virtual padding"), ("label", "virtual_padding"), ("size", object["virtual memory size"] - object["size"]), ("objnum", object["num"])]))
	#	for offset in range(object["size"], object["virtual memory size"]):
	#		disassembly.append(generate_define_byte(offset, 0, comment=True if (object["type"] == "data") else False))
	#	insert_structure_item(structure, OrderedDict([("type", "virtual padding end"), ("offset", object["virtual memory size"]), ("name", "Virtual padding"), ("label", "virtual_padding")]))

	# Append object end to structure
	insert_structure_item(structure, OrderedDict([("type", "object end"), ("offset", object["virtual memory size"] if (object["virtual memory size"] > object["size"]) else object["size"]), ("name", "Object %d" % object["num"]), ("label", "object_%d" % object["num"]), ("objnum", object["num"])]))

	# Print stats, store results
	print_normal("Disassembly: %d lines, %d bytes" % (len(disassembly), len(str.join(os.linesep, disassembly))))
	print_structure_stats(structure)
	object["disassembly1"] = disassembly
	object["structure"] = structure


# Generates formatted disassembly, i.e. plain disassembly + disassembly structure -> formatted disassembly
def generate_formatted_disassembly(object, globals, data_object):
	print_light("Generating formatted disassembly of object %d:" % object["num"])

	# tbd
	if (object["type"] == "code"):
		# Prepare replace branch addresses with labels: generate dict offset -> list of structure targets
		branches = OrderedDict()
		for item in object["structure"]:
			if (not item["type"] in ("function", "branch")):
				continue
			if (not item["offset"] in branches):
				branches[item["offset"]] = []
			branches[item["offset"]].append(item)
		#content = generate_pprint(branches)
		#write_file("/tmp/%s", "testing_branches.txt", content)

		# Prepare replace 'cs:0x...' references with cs variables
		cs_vars = OrderedDict()
		for item in globals:
			#if (item["segment"] != object["num"] or item["type"] != "data"):
			if (item["segment"] != object["num"]): # also gather 'code' items, e.g. '_Alphabet'
				continue
			if (not item["offset"] in cs_vars):
				cs_vars[item["offset"]] = []
			cs_vars[item["offset"]].append(item)
		#content = generate_pprint(cs_vars)
		#write_file("/tmp/%s", "testing_cs_vars.txt", content)

		# Prepare replace 'ds:0x...' references with ds variables
		ds_vars = OrderedDict()
		if (data_object != None):
			for item in globals:
				if (item["segment"] != data_object or item["type"] != "data"):
					continue
				if (not item["offset"] in ds_vars):
					ds_vars[item["offset"]] = []
				ds_vars[item["offset"]].append(item)
			#content = generate_pprint(ds_vars)
			#write_file("/tmp/%s", "testing_ds_vars.txt", content)

		print_normal("Branches: %d, cs variables: %d, ds variables: %d" % (len(branches), len(cs_vars), len(ds_vars)))

	# Process disassembly (for i in ...) and structure (while struct_index < ...)
	disassembly = []
	current_offset = 0
	struct_index = 0
	for i in range(0, len(object["disassembly1"]) + 1):

		# All loop iterations except last one
		if (i < len(object["disassembly1"])):
			line = object["disassembly1"][i]
			asm = split_asm_line(line)
			if (asm == None):
				print_warn("Invalid assembler line (line %d): %s" % (i+1, line))
			elif (asm["type"] == "normal" or asm["type"] == "hex"):
				current_offset = asm["offset"]

			# tbd
			if (object["type"] == "code"):
				# Replace branch addresses with labels
				if (asm != None and asm["type"] == "normal" and (asm["command"] == "call" or asm["command"].startswith("j"))):
					match = re.match("^0x([0-9a-fA-F]+)$", asm["arguments"].strip())
					if (match == None):
						#print_warn("Failed to match address (line %d): %s" % (i+1, line))
						pass
					else:
						addr_str = match.group(0)
						addr_val = int(match.group(1), 16)
						if (addr_val in branches):
							line = line.replace(addr_str, branches[addr_val][0]["label"])
						else:
							print_error("[should-never-occur] Replace branch targets: no match for offset 0x%x: %s" % (addr_val, line))

				# Replace 'cs:0x...' references with cs variables
				if (asm["type"] == "normal"):
					#match = re.search("(cs:0x([0-9a-fA-F]+))", asm["arguments"])
					match = re.search("cs:(0x([0-9a-fA-F]+))", asm["arguments"])
					if (match == None):
						match = re.search("cs:\[.+[+-](0x([0-9a-fA-F]+))\]", asm["arguments"])
					if (match == None):
						#print_warn("Failed to match address (line %d): %s" % (i+1, line))
						pass
					else:
						addr_str = match.group(1)
						addr_val = int(match.group(2), 16)
						if (addr_val in cs_vars):
							#print_warn("Replacing cs:0x variable:    %s -> %s" % (line, cs_vars[addr_val][0]["name"]))
							line = line.replace(addr_str, cs_vars[addr_val][0]["name"])
						else:
							#print_error("replace cs variables: no match for offset 0x%x: %s" % (addr_val, line))
							pass

				# Replace 'ds:0x...' references with ds variables
				if (asm["type"] == "normal"):
					#match = re.search("(ds:0x([0-9a-fA-F]+))", asm["arguments"])
					match = re.search("ds:(0x([0-9a-fA-F]+))", asm["arguments"])
					if (match == None):
						match = re.search("ds:\[.+[+-](0x([0-9a-fA-F]+))\]", asm["arguments"])
					#if (match == None): # TODO: try re-enabling this once relocation + fixup is in place; without, this gives way to many false-positives
					#	match = re.search("(?<!s:)\[.+[+-](0x([0-9a-fA-F]+))\]", asm["arguments"]) # (?<!s:) -> negative lookahead -> may not preceded by 's:' -> https://stackoverflow.com/a/47886935
					if (match == None):
						#print_warn("Failed to match address (line %d): %s" % (i+1, line))
						pass
					else:
						addr_str = match.group(1)
						addr_val = int(match.group(2), 16)
						if (addr_val in ds_vars and addr_str != "0x0"): # 0x0 -> exception for [<reg>+0x0], which appears quite often and would be replaced by '__nullarea'
							#print_warn("Replacing ds:0x variable:    %s -> %s" % (line, ds_vars[addr_val][0]["name"]))
							line = line.replace(addr_str, ds_vars[addr_val][0]["name"])
						else:
							#print_error("replace ds variables: no match for offset 0x%x: %s" % (addr_val, line))
							pass

				# Replace indirect address + base with ds variables
				# e.g. '  10d:  83 3c 9d 08 98 04 00 00   cmp    DWORD PTR [ebx*4+0x49808],0x0' -> [ebx*4+0x49808] > [ebx*4+smp]
				#       '6767:  8b 3c bd 08 9f 04 00      mov    edi,DWORD PTR [edi*4+0x49f08]'
				# NOTE: merged this into replacement routine above (see third regex)
				#if (asm != None and asm["type"] == "normal"):
				#	match = re.search("(?<!s:)\[.+[+-](0x([0-9a-fA-F]+))\]", asm["arguments"]) # (?<!s:) -> negative lookahead -> may not preceded by 's:' -> https://stackoverflow.com/a/47886935
				#	if (match == None):
				#		#print_warn("Failed to match address (line %d): %s" % (i+1, line))
				#		#continue
				#		pass
				#	else:
				#		addr_str = match.group(1)
				#		addr_val = int(match.group(2), 16)
				#		if (addr_val in ds_vars and not ds_vars[addr_val][0]["name"] == "__nullarea"):
				#			#print_warn("Replacing [...+0x] variable: %s -> %s" % (line, ds_vars[addr_val][0]["name"]))
				#			line = line.replace(addr_str, ds_vars[addr_val][0]["name"])
				#		else:
				#			#print_error("replace ds variables: no match for offset 0x%x: %s" % (addr_val, line))
				#			pass

		# Last loop iteration
		else:
			current_offset = object["virtual memory size"] if (object["virtual memory size"] > object["size"]) else object["size"]

		# Process structure items for current offset + those we may have missed in between last offset and current offset
		while (struct_index < len(object["structure"]) and object["structure"][struct_index]["offset"] <= current_offset):
			item = object["structure"][struct_index]

			pre = []
			if (item["offset"] < current_offset):
				print_warn("Misplaced item '%s' at offset 0x%x" % (item["name"], current_offset))
				pre = ["; misplaced item, should be at offset 0x%0x" % item["offset"]]

			if (item["type"] == "object start"):
				disassembly += generate_comment_box(pre=pre, body=["", "Object %d" % item["objnum"], ""])
			elif (item["type"] == "object end"):
				disassembly += generate_comment_box(pre=[""] + pre, body=["", "End of object %d" % item["objnum"], ""])
			elif (item["type"] == "bad code start"):
				disassembly += generate_comment_box(pre=pre, body=["bad code (%s):" % item["subtype"]])
				for context in item["context"]:
					disassembly.append(";%s" % (context[1:]))
				disassembly += generate_comment_box(body=["padding data (%d bytes):" % item["padding"]])
			elif (item["type"] == "bad code end"):
				disassembly += generate_comment_box(pre=pre, body=["end of padding / bad code"])
			elif (item["type"] == "hint start"):
				if (item["subtype"] == "data"):
					#body = ["Hint %d (%s, %s, %d bytes):" % (item["hintnum"], item["subtype"], item["subtype2"], item["size"])] + (["%s" % item["comment"]] if ("comment" in item) else [])
					body = ["Hint %d (%s, %s, %d bytes):" % (item["hintnum"], item["subtype"], item["subtype2"], item["size"])] + (["%s" % line for line in item["comment"].split("\\n")] if ("comment" in item) else [])
				disassembly += generate_comment_box(pre=pre, body=body, width=40)
			elif (item["type"] == "hint end"):
				disassembly += generate_comment_box(pre=pre, body=["End of hint"], width=40)
			elif (item["type"] == "virtual padding start"):
				disassembly += generate_comment_box(pre=[""] + pre, body=["", "End of actual data of object %d" % item["objnum"], "Start of padding data to match virtual size (%d bytes)" % item["size"], ""], post=[""])
			elif (item["type"] == "virtual padding end"):
				disassembly += generate_comment_box(pre=[""] + pre, body=["", "End of padding data to match virtual size", ""])
			elif (item["type"] == "module"):
				disassembly += generate_comment_box(pre=[""] + pre, body=["", "Module %d: %s" % (item["modnum"], item["name"]), ""])
			elif (item["type"] == "function"):
				disassembly += generate_comment_box(pre=[""] + pre, body=["Function '%s'" % item["name"]], width=40)
				disassembly.append("%s:" % item["label"])
			elif (item["type"] == "branch"):
				disassembly += pre
				disassembly.append("%s:" % item["label"])
			elif (item["type"] == "variable"):
				disassembly += pre
				if ("sizes" in item):
					disassembly.append("%-50s ; %s: %s" % (item["label"] + ":", "sizes" if (len(item["sizes"]) > 1) else "size", str.join(", ", item["sizes"])))
				else:
					disassembly.append("%s:" % item["label"])
			else:
				print_error("[should-never-occur] Invalid structure type '%s'" % item["type"])

			struct_index += 1

		# Copy disassembly line
		if (i < len(object["disassembly1"])):
			disassembly.append(line)

	# Store results
	print_normal("Size of formatted disassembly: %d lines, %d bytes" % (len(disassembly), len(str.join(os.linesep, disassembly))))
	object["disassembly2"] = disassembly


# disassembler main
def disassemble_objects(objdump_exec, wdump, data_object, outfile_template):
	print_light("Disassembling objects:")
	disasm = OrderedDict([("objects", []), ("modules", []), ("globals", [])])


	# TODO: put this after 'preprocess objects'; set 'automatic data object' to 'false' in preprocess, then set it to true here for data object
	#       -> makes life easier as we can use disasm["objects"] for data object verification

	# If data object was not specified by user on command line, try to locate automatic data object hint in wdump data
	if (data_object == None):
		print_normal("Locating automatic data object hint...")
		if (dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "object # for automatic data object")):
			data_object = wdump["linear exe header (os/2 v2.x) - le"]["data"]["object # for automatic data object"]
			print_normal("Located automatic data object hint: object %d" % data_object)
		if (data_object == None):
			print_warn("Failed to locate automatic data object hint")

	# Check if data object (either user-specified or from automatic data object hint) is valid, i.e. it exists and is of type 'data'
	if (data_object != None):
		print_normal("Verifying data object %d..." % data_object)
		if (data_object in wdump["object table"]["data"]):
			object = wdump["object table"]["data"][data_object]
			object_type = "code" if ("executable" in object["flags"].lower()) else "data"
			if (object_type == "data"):
				print_normal("Data object %d verified" % data_object)
			else:
				print_warn("Object %d has wrong type: expected 'data', got '%s'" % (data_object, object_type))
				data_object = None
		else:
			print_warn("Object %d not found in object table" % data_object)
			data_object = None

	# Do we have a data object by now?
	if (data_object == None):
		print_warn("No data object specified. Data segment reference analysis/replacement disabled.")


	# Preprocess objects: accumulate data over pages/segments, determine size, determine type, add hints, add flag for automatic data object, sort
	# TODO: this should be the perfect place to process/apply fixups
	if ("object table" in wdump):
		print_normal("Preprocessing objects...")
		for object in wdump["object table"]["data"].values():
			object_size = 0
			object_data = b''
			for page in object["pages"].values():
				page_size = 0
				page_data = b''
				for segment in page["segments"].values():
					segment_size = len(segment["data"])
					page_size += segment_size
					page_data += segment["data"]
				object_size += page_size
				object_data += page_data
			object_type = "code" if ("executable" in object["flags"].lower()) else "data"
			object_hints = []
			if ("object hints" in wdump and object["num"] in wdump["object hints"]["data"]):
				for entry in wdump["object hints"]["data"][object["num"]]["entries"].values():
					object_hints.append(OrderedDict([(key, entry[key]) for key in entry.keys()]))
				object_hints.sort(key=lambda item: item["offset"])
			disasm["objects"].append(OrderedDict([(key, object[key]) for key in object.keys() if (key != "pages")] + ([("automatic data object", True if (data_object != None and object["num"] == data_object) else False)] if (object_type == "data") else []) + [("size", object_size), ("data", object_data), ("type", object_type), ("hints", object_hints), ("structure", []), ("disassembly1", []), ("disassembly2", [])])) # https://stackoverflow.com/a/32895702
		disasm["objects"].sort(key=lambda item: item["num"])

	# Preprocess modules: accumulate modules over subsections, accumulate address info over subsections and add to modules, sort
	# NOTE: temporarily using OrderedDict for modules to facilitate adding address info; reduced to list at end
	if ("module info" in wdump):
		print_normal("Preprocessing modules...")
		modules = OrderedDict()
		for subsec in wdump["module info"]["data"].values():
			for module in subsec["data"].values():
				modules[module["num"]] = OrderedDict([(key, module[key]) for key in module.keys() if (not key in ("locals", "types", "lines"))] + [("offsets", [])])
		for subsec in wdump["addr info"]["data"].values():
			for segment in subsec["data"]:
				for entry in segment["entries"].values():
					if (not entry["module"] in modules):
						print_error("[should-never-occur] Invalid module index %d" % entry["module"])
						continue
					modules[entry["module"]]["offsets"].append(OrderedDict([("segment", segment["segment"]), ("offset", entry["offset"]), ("size", entry["size"])]))
		for module in modules.values():
			module["offsets"].sort(key=lambda item: (item["segment"], item["offset"]))
		modules = list(modules.values())
		modules.sort(key=lambda item: item["num"])
		disasm["modules"] = modules

	# Preprocess globals: accumulate globals over subsections, sort
	if ("global info" in wdump):
		print_normal("Preprocessing globals...")
		for subsec in wdump["global info"]["data"].values():
			for global_ in subsec["data"]:
				disasm["globals"].append(OrderedDict([(key, global_[key]) for key in global_.keys()]))
		disasm["globals"].sort(key=lambda item: (item["segment"], item["offset"]))

	# Disassemble code objects
	# NOTE: these need to be done first as they might add missing data segment references for automatic data object
	for object in disasm["objects"]:
		if (object["type"] != "code"):
			continue
		disassemble_code_object(object, disasm["modules"], disasm["globals"], objdump_exec, data_object)

	# Disassemble data objects
	for object in disasm["objects"]:
		if (object["type"] != "data"):
			continue
		disassemble_data_object(object, disasm["modules"], disasm["globals"], data_object)

	# Format disassembly (all objects)
	for object in disasm["objects"]:
		generate_formatted_disassembly(object, disasm["globals"], data_object)

	# Write results to files
	print_light("Writing disassembly results to files...")
	write_file(outfile_template, "disasm_data.txt", generate_pprint(disasm))
	for object in disasm["objects"]:
		write_file(outfile_template, "object_%d_data.bin" % object["num"], object["data"])
		write_file(outfile_template, "object_%d_disassembly_structure.txt" % object["num"], generate_pprint(object["structure"]))
		write_file(outfile_template, "object_%d_disassembly_plain.asm" % object["num"], object["disassembly1"])
		write_file(outfile_template, "object_%d_disassembly_formatted.asm" % object["num"], object["disassembly2"])
	# TESTING Write wdump data to file again; can be used for diff to make sure wdump data has not been modified; disassembler should
	#         not touch wdump data, should only work on 'disasm'
	#write_file(outfile_template, "wdump_output_parsed2.txt", generate_pprint(wdump))

	# Return results
	return disasm



# ------------------------------------------------------------------------------
#                                                                              -
#  Main                                                                        -
#                                                                              -
# ------------------------------------------------------------------------------

# Main function
def main():
	prog_name = "Watcom Decompilation Tool (wcdctool)"
	prog_desc = "Tool for decompiling protected mode executables created with Watcom toolchain."

	# Process command line (1)
	msg_error = "Invalid command line. Use %s for usage information."
	msg_usage = "Usage: %s [OPTION]... %s\n\n" + prog_name + "\n" + prog_desc + "\n\nOptions:"
	cmd_opts = [
		{ "type": "normal", "name": "wdump_exec", "short": "-wde", "long": "--wdump-executable", "arg": "path", "default": "wdump", "help": "Path to wdump executable" },
		{ "type": "normal",	"name": "objdump_exec", "short": "-ode", "long": "--objdump-executable", "arg": "path", "default": "objdump", "help": "Path to objdump executable" },
		{ "type": "normal", "name": "wdump_output", "short": "-wdo", "long": "--wdump-output", "arg": "file", "help": "Read wdump output from file instead of running wdump" },
		{ "type": "normal", "name": "wdump_add_output", "short": "-wao", "long": "--wdump-additional-output", "arg": "file", "help": "Read additional wdump output from file" },
		{ "type": "normal", "name": "data_object", "short": "-do", "long": "--data-object", "arg": "path", "help": "Number of object ds:... references point to" },
		{ "type": "normal", "name": "outdir", "short": "-o", "long": "--outdir", "arg": "path", "help": "Output directory for generated contents" },
		{ "type": "switch", "name": "debug", "short": "-d", "long": "--debug", "arg": "path", "help": "Drop to interactive debugger before exiting" },
		{ "type": "switch", "name": "shell", "short": "-s", "long": "--shell", "arg": "path", "help": "Drop to interactive shell before exiting" },
		{ "type": "help", "name": "help", "short": "-h", "long": "--help", "help": "Display this message" },
		{ "type": "positional", "name": "input_file", "display": "file", "nargs": 1, "help": "Input file" },
	]
	parser = ArgumentParser(cmd_opts, msg_error=msg_error, exc_error=2, msg_usage=msg_usage, exc_usage=0)
	args = parser.parse_args()

	# Process command line (2)
	if (args.data_object != None):
		try:
			args.data_object = int(args.data_object)
		except ValueError:
			print_error("Argument for option -do/--data-object is not an integer: %s" % args.data_object)
			return 2

	# Check command availability
	if (args.wdump_output == None and shutil.which(args.wdump_exec) == None):
		print_error("Unable to find wdump command ('%s') Either provide its location (-wde/--wdump-executable) or provide pre-generated wdump output (-wdo/--wdump-output)." % args.wdump_exec)
		return 1
	if (shutil.which(args.objdump_exec) == None):
		print_error("Unable to find objdump command ('%s'). Provide its location using -ode/--objdump-executable." % args.objdump_exec)
		return 1

	# Print title
	print_light(prog_name)
	print_normal()

	# Generate output file template
	outfile_template = args.outdir + os.path.sep if (args.outdir != None) else ""
	outfile_template += os.path.basename(args.input_file) + "_%s"

	# Parse wdump output
	wdump = wdump_parse_output(args.input_file, args.wdump_exec, args.wdump_output, args.wdump_add_output, outfile_template)
	if (wdump == None):
		return 1

	# Detect and extract DOS/4G(W) stub / payload
	# NOTE: this is necessary as wdump will only yield usable results for the payload
	if (dict_path_exists(wdump, "dos/16m exe header", "data", "offset of possible next spliced .exp")):
		offset = wdump["dos/16m exe header"]["data"]["offset of possible next spliced .exp"]
		print_normal()
		print_light("Extracting DOS/4G(W) stub / payload:")
		print_normal("Offset of DOS/4G(W) payload: 0x%x" % offset)
		try:
			print_normal("Opening input file to read data...")
			with open(args.input_file, "rb") as infile:
				print_normal("Reading DOS/4G(W) stub data (offset 0x0 - 0x%x)..." % (offset-1))
				stub_data = infile.read(offset)
				print_normal("Reading DOS/4G(W) payload data (offset 0x%x - EOF)..." % offset)
				payload_data = infile.read()
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			return 1
		print_normal("Writing DOS/4G(W) stub data to file (%d bytes)..." % len(stub_data))
		write_file(outfile_template, "dos4g_stub.exe", stub_data)
		print_normal("Writing DOS/4G(W) payload data to file (%d bytes)..." % len(payload_data))
		write_file(outfile_template, "dos4g_payload.exe", payload_data)
		args.input_file = outfile_template % "dos4g_payload.exe"
		print_normal("Running wdump parser for DOS/4G(W) payload...")
		print_normal()
		wdump = wdump_parse_output(args.input_file, args.wdump_exec, args.wdump_output, args.wdump_add_output, outfile_template)
		if (wdump == None):
			return 1

	# Detect and extract linear executable stub / payload
	# NOTE: we only do this to allow further examination of the extracted files, they are not used anywhere in this script
	if (dict_path_exists(wdump, "linear exe header (os/2 v2.x) - le", "data", "file offset")):
		offset = wdump["linear exe header (os/2 v2.x) - le"]["data"]["file offset"]
		print_normal()
		print_light("Extracting linear executable stub / payload:")
		print_normal("Offset of linear executable payload: 0x%x" % offset)
		try:
			print_normal("Opening input file to read data...")
			with open(args.input_file, "rb") as infile:
				print_normal("Reading linear executable stub data (offset 0x0 - 0x%x)..." % (offset-1))
				stub_data = infile.read(offset)
				print_normal("Reading linear executable payload data (offset 0x%x - EOF)..." % offset)
				payload_data = infile.read()
		except Exception as exception:
			print_error("Error: %s" % str(exception))
			return 1
		print_normal("Writing linear executable stub data to file (%d bytes)..." % len(stub_data))
		write_file(outfile_template, "linear_executable_stub.exe", stub_data)
		print_normal("Writing linear executable payload data to file (%d bytes)..." % len(payload_data))
		write_file(outfile_template, "linear_executable_payload.bin", payload_data)

	# Read and decode fixup / relocation data
	print_normal()
	fixup = fixup_relocation_read_decode(wdump, args.input_file, outfile_template)

	# Disassemble objects
	print_normal()
	disasm = disassemble_objects(args.objdump_exec, wdump, args.data_object, outfile_template)

	# Drop to interactive debugger/shell if requested
	if (args.debug == True or args.shell == True):
		print_normal()
		print_light("Dropping to interactive %s..." % ("debugger" if args.debug else "shell"))
		print_light("Generated data is stored in locals 'wdump', 'fixup' and 'disasm'.")
		shell_locals={ "wdump": wdump, "fixup": fixup, "disasm": disasm }
		if (args.debug == True):
			import pdb
			pdb.run("", globals=globals(), locals=shell_locals)
		else:
			import code
			code.interact(banner="", local=shell_locals, exitmsg="")

	# Write log to file
	print_normal()
	print_light("Writing log to file...")
	log = [ item for item in print_log ]
	write_file(outfile_template, "log_plain.txt", [ item["text"] + (os.linesep if (item["end"] == "\n") else item["end"]) for item in log ], joinstr="")
	write_file(outfile_template, "log_color.txt", [ item["esc1"] + item["text"] + item["esc2"] + (os.linesep if (item["end"] == "\n") else item["end"]) for item in log ], joinstr="")

	# Return home safely
	return 0

# Call main function
if (__name__ == "__main__"):
	sys.exit(main())
