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
def fit_activity ( dev, track ):
  lmsg = 0
  data = ''
  time = None
  ptp  = None

  # Create records (TODO: dynamic field list)
  rec_fields = [ 'timestamp', 'position_lat', 'position_long', 'altitude',
                 'heart_rate', 'cadence', 'speed', 'temperature' ]
  rec_data   = []
  first   = True
  for seg in track:
    seg = list(seg)
    if first:
      first = False
      if len(seg) < 5:
        if not [1 for tp, lp in seg if tp is None]:
          continue
    for tp, lp in seg:
      if not lp: continue
      if not tp and lp.speed < 2.0: tp = ptp
      if not tp: continue
      ptp = tp
      if time is None: time = lp.timestamp
      r = [ time2timestamp(lp.timestamp),
            deg2semicircle(tp.latitude), 
            deg2semicircle(tp.longitude),
            tp.elevation,
            lp.heartrate     or 0,
            lp.cadence       or 0,
            kph2mps(lp.speed or 0.0),
            lp.temperature   or 0]
      rec_data.append(r)

  # file_id
  data += fit_msg(
    local_msg  = lmsg,
    msg_name   = 'file_id',
    msg_fields = [
      'type', 'manufacturer', ('product', 'garmin_product'),
      'serial_number', 'time_created'
    ],
    msg_data   = [
      [
        'activity', 'garmin', 'edge500',
        int(dev.get_serial()) & 0xFFFFFFFF, time2timestamp(time),
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

if __name__ == '__main__':
  load(sys.argv[1])

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
