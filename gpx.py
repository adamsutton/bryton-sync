#!/usr/bin/env python
#
# bryton-sync.py - Main Application
#
# Copyright (C) 2014 Adam Sutton <dev@adamsutton.me.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# ###########################################################################
# Imports
# ###########################################################################

import time, datetime

# ###########################################################################
# Functions
# ###########################################################################

#
# Convert time
#
def time2isoformat ( t ):
  return datetime.datetime.utcfromtimestamp(int(t)).isoformat() + 'Z'

#
# Output GPX activity
#

def gpx_activity ( track ):

  # Header
  gpx = '<?xml version="1.0" encoding="UTF-8" standalone="no" ?>\n'
  gpx += '<gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxx="http://www.garmin.com/xmlschemas/GpxExtensions/v3" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" creator="Oregon 400t" version="1.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd http://www.garmin.com/xmlschemas/GpxExtensions/v3 http://www.garmin.com/xmlschemas/GpxExtensionsv3.xsd http://www.garmin.com/xmlschemas/TrackPointExtension/v1 http://www.garmin.com/xmlschemas/TrackPointExtensionv1.xsd">\n'
  gpx += '  <metadata>\n'
  gpx += '    <time>%s</time>\n' % time2isoformat(track[0]['timestamp'])
  gpx += '  </metadata>\n'

  # Track Begin
  gpx += '  <trk>\n'
  gpx += '    <name>GPX Backup of FIT</name>\n'
  gpx += '    <trkseg>\n'


  # Track points
  for p in track:
    gpx += '      <trkpt lat="%0.6f" lon="%0.6f">\n' % (p['latitude'], p['longitude'])
    gpx += '        <ele>%0.6f</ele>\n' % p['altitude']
    gpx += '        <time>%s</time>\n' % time2isoformat(p['timestamp'])
    gpx += '        <extensions>\n'
    gpx += '          <gpxtpx:TrackPointExtension>\n'
    if 'cadence' in p:
      gpx += '            <gpxtpx:cad>%d</gpxtpx:cad>\n' % p['cadence']
    if 'heartrate' in p:
      gpx += '            <gpxtpx:hr>%d</gpxtpx:hr>\n' % p['heartrate']
    if 'temperature' in p:
      gpx += '            <gpxtpx:atemp>%0.2f</gpxtpx:atemp>\n' % p['temperature']
    gpx += '          </gpxtpx:TrackPointExtension>\n'
    gpx += '        </extensions>\n'
    gpx += '      </trkpt>\n'  

  # Track End / Footer
  gpx += '    </trkseg>\n'
  gpx += '  </trk>\n'
  gpx += '</gpx>\n'

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
