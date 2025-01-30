# Copyright (c) 2009, David Buxton <david@gasmark6.com>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
# 
#     * Redistributions of source code must retain the above copyright
# notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS
# IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""Tools to convert between Python datetime instances and Microsoft times.
"""


# http://support.microsoft.com/kb/167296
# How To Convert a UNIX time_t to a Win32 FILETIME or SYSTEMTIME
EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
HUNDREDS_OF_NANOSECONDS = 10000000


def timestamp2filetime(ts):
	"""Converts a datetime to Microsoft filetime format. If the object is
	time zone-naive, it is forced to UTC before conversion.

	>>> import calendar
	>>> "%.0f" % timestamp2filetime(calendar.timegm((2009, 7, 25, 23, 0, 0, 0, 0, 0)))
	'128930364000000000'

	>>> "%.0f" % timestamp2filetime(calendar.timegm((1970, 1, 1, 0, 0, 0, 0, 0)))
	'116444736000000000'

	>>> timestamp2filetime(calendar.timegm((2009, 7, 25, 23, 0, 0, 0, 0, 0)) + 0.001)
	128930364000010000
	"""
	return int(ts * HUNDREDS_OF_NANOSECONDS) + EPOCH_AS_FILETIME


def filetime2timestamp(ft):
	"""Converts a Microsoft filetime number to a Python datetime. The new
	datetime object is time zone-naive but is equivalent to tzinfo=utc.

	>>> filetime2timestamp(116444736000000000)
	0.0

	>>> filetime2timestamp(128930364000000000)
	1248562800.0
	
	>>> filetime2timestamp(128930364000001000)
	1248562800.0001
	"""
	# Get seconds and remainder in terms of Unix epoch
	return (ft - EPOCH_AS_FILETIME) / float(HUNDREDS_OF_NANOSECONDS)


if __name__ == "__main__":
	import doctest
	
	doctest.testmod()

