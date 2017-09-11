#!/usr/bin/env python
#
# fit.py - FIT file generator
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

# System
import os, sys, time, re
import struct
from datetime import datetime

# Path
d = os.path.dirname(sys.argv[0]) or '.'
sys.path.insert(0, d + '/python-fitparse')

# fitparse
from fitparse.profile import MESSAGE_TYPES, FIELD_TYPES
from fitparse.utils   import calc_crc

# ###########################################################################
# FIT type conversion
# ###########################################################################

def time2timestamp ( tm ):
  return int(tm - 631065600)

def deg2semicircle ( deg ):
  sc  = deg / 180.0
  sc *= (2 ** 31)
  return int(sc)

def kph2mps ( kph ):
  mps = (kph / 3.6)
  return mps

# ###########################################################################
# FIT file generation
# ###########################################################################

#
# Generate message
#
def fit_msg ( local_msg, msg_name, msg_fields, msg_data = None ):
  msg_type    = [m for m in MESSAGE_TYPES.values() if m.name == msg_name][0]
  field_types = []

  # Convert msg_fields
  for i in range(len(msg_fields)):
    if type(msg_fields[i]) != type(()):
      msg_fields[i] = (msg_fields[i], None)

  # Definition Message
  s =  struct.pack('<B',  0x40 | local_msg)
  s += struct.pack('<xB', 0)
  s += struct.pack('<HB', msg_type.mesg_num, len(msg_fields)) 
  for n, sf in msg_fields:
    fn = [f for f in msg_type.fields if msg_type.fields[f].name == n][0]
    ft = msg_type.fields[fn]
    bt = ft.type
    if hasattr(bt, 'base_type'):
      bt = bt.base_type
    if hasattr(ft, 'subfields') and ft.subfields:
      sf = [f for f in ft.subfields if f.name == sf][0]
    s += struct.pack('<3B', fn, bt.size, bt.identifier)
    if sf: ft = sf
    field_types.append(ft)
  
  # Data
  if msg_data:
    for d in msg_data:
      s += struct.pack('<B', 0x00 | local_msg)
      for fv, ft in zip(d, field_types):
        bt = ft.type
        if hasattr(bt, 'values') and bt.values:
          for v in bt.values:
            if bt.values[v] == fv:
              fv = v
              break
        if hasattr(ft, 'offset') and ft.offset:
          fv += ft.offset
        if hasattr(ft, 'scale')  and ft.scale:
          fv *= ft.scale
        if hasattr(bt, 'base_type'):
          bt = bt.base_type
        s += struct.pack('<'+bt.fmt, fv)

  return s

#
# Generate header
#
def fit_hdr ( data ): 
  return struct.pack('<2BHI4s', 12, 16, 152, len(data), '.FIT') 

#
# Generate CRC
#
def fit_crc ( data ):
  return struct.pack('<H', calc_crc(data, 0))

#
# Generate activity file
#
def fit_activity ( track ):
  lmsg = 0
  data = ''

  # Create records (TODO: dynamic field list)
  rec_fields = [ 'timestamp', 'position_lat', 'position_long', 'altitude',
                 'heart_rate', 'cadence', 'speed', 'temperature' ]
  rec_data   = []
  for p in track:
    r = [ time2timestamp(p['timestamp']),
          deg2semicircle(p['latitude']), 
          deg2semicircle(p['longitude']),
          p['altitude'],
          p['heartrate']      if 'heartrate'   in p else 0,
          p['cadence']        if 'cadence'     in p else 0,
          kph2mps(p['speed']) if 'speed'       in p else 0,
          p['temperature']    if 'temperature' in p else 0,
        ]
    rec_data.append(r)

  # file_id
  data += fit_msg(
    local_msg  = lmsg,
    msg_name   = 'file_id',
    msg_fields = [
      'type', 
      'manufacturer',
      ('product', 'garmin_product'),
      'serial_number',
      'time_created'
    ],
    msg_data   = [
      [
        'activity',
        'garmin',
        'edge500',
        0x00000000,
        time2timestamp(track[0]['timestamp']),
      ],
    ]
  )
  lmsg += 1
  
  # records
  data += fit_msg(
    local_msg  = lmsg,
    msg_name   = 'record',
    msg_fields = rec_fields,
    msg_data   = rec_data
  )
  lmsg += 1
  
  # Add header/footer
  data =  fit_hdr(data) + data
  data += fit_crc(data)

  return data

# ###########################################################################
# Test
# ###########################################################################

# ###########################################################################
# Main
# ###########################################################################

if __name__ == '__main__':
  import json
  from optparse import OptionParser

  # Command line
  optp = OptionParser()
  (opts, args) = optp.parse_args()
  #print opts, args

  # Load track
  track = json.loads(open(args[0]).read())

  # Convert to FIT
  fit   = fit_activity(track)

  # Output to file
  if len(args) > 1:
    open(args[1], 'w').write(fit)
  
  # Output to stdout
  else:
    print fit

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
