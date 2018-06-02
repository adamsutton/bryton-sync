#!/usr/bin/env python
#
# bryton-sync.py - Track manipulation
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

import copy

# ###########################################################################
# Functions
# ###########################################################################

#
# Calculate haversine distnace between 2 points
#
def haversine(lon1, lat1, lon2, lat2):
  from math import radians, cos, sin, asin, sqrt

  # convert decimal degrees to radians
  lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

  # haversine formula
  dlon = lon2 - lon1
  dlat = lat2 - lat1
  a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
  c = 2 * asin(sqrt(a))

  # 6367 km is the radius of the Earth
  km = 6367 * c
  return km


#
# Convert native bryton format to internal format with linear points
#
# I.e. no segments etc.. and combiend track and lap points
#

def convert ( track ):
  ptp   = None # previous track point
  start = None
  ret   = []
  dist  = 0.0
  plp   = None

  for seg in track:
    for tp, lp in seg:
      if not lp: continue # faulty (very rare)
      if tp and tp.timestamp != lp.timestamp: continue # faulty
      if not start:
        start = lp.timestamp
      if plp and lp.speed is not None:
        t = lp.timestamp - plp.timestamp
        dist += lp.speed * t
      d = {
        'timestamp' : lp.timestamp,
      }
      if tp:
        d['latitude']    = tp.latitude
        d['longitude']   = tp.longitude
        d['altitude']    = tp.elevation
      if lp.temperature is not None:
        d['temperature'] = lp.temperature
      if lp.heartrate is not None:
        d['heartrate']   = lp.heartrate
      if lp.cadence is not None:
        d['cadence']     = lp.cadence
      if lp.speed is not None:
        d['speed']       = lp.speed
      if dist:
        d['distance']    = dist
      ret.append(d)
      plp = lp

  return { 'timestamp' : start, 'track' : ret, 'static' : False }

#
# Perform all fixups on a track
#
def fixup ( track, conf ):
  track = fixup_static(track, conf)
  if not track['static']:
    track = fixup_crop(track, conf)
    track = fixup_missing(track, conf)
    track = fixup_extrapolate(track, conf)
    track = fixup_speed(track, conf)
  track['timestamp'] = track['track'][0]['timestamp']
  return track

#
# Check for whether this is a static track
#
def fixup_static ( track, conf ):
  static = True
  prev   = None
  for p in track['track']:
    if 'latitude' not in p: continue
    if prev is None: prev = p
    d = abs(haversine(prev['longitude'], prev['latitude'],
                      p['longitude'], p['latitude']))
    if d > conf['move_distance']:
      static = False
      break
  track['static'] = static
  return track

#
# Calculate the speed at each pint
#
def fixup_speed ( track, conf ):
  prev = None
  for p in track['track']:
    if 'latitude' not in p: continue
    if prev is None: prev = p
    dd = abs(haversine(prev['longitude'], prev['latitude'],
                       p['longitude'], p['latitude']))
    dt = p['timestamp'] - prev['timestamp']
    if dt:
      p['speed'] = (dd / dt) * 3600.0
    else:
      p['speed'] = 0
    prev = p
  return track

#
# Remove points without GPS
#
def fixup_missing ( track, conf ):
  ret = []
  for p in track['track']:
    if 'latitude' not in p: continue  
    ret.append(p)
  track['track'] = ret
  return track

#
# Extrapolate points as per configuration
#
def fixup_extrapolate ( track, conf ):
  period = int(conf['update_period'])
  ret    = [ track['track'][0] ]

  for p in track['track'][1:]:
    t     = ret[-1]['timestamp']
    dt    = float(p['timestamp'] - t)
    ds    = (p['speed'] - ret[-1]['speed']) / dt
    llf   = ((p['speed'] + ret[-1]['speed']) / 2) * dt
    dlat  = (p['latitude'] - ret[-1]['latitude'])
    dlon  = (p['longitude'] - ret[-1]['longitude'])
    delta = {}
    for k in p:
      if k not in ret[-1]: continue
      delta[k] = (p[k] - ret[-1][k]) / dt
    t += period
    while t < p['timestamp']:
      np = copy.copy(ret[-1])
      np['timestamp'] = t
      for k in np:
        if k in [ 'timestamp' ]: continue
        if k not in delta:       continue
        np[k] = ret[-1][k] + delta[k]
      np['speed']     = ret[-1]['speed'] + ds
      i               = ((ret[-1]['speed'] + np['speed']) / 2.0) / llf
      np['latitude']  = ret[-1]['latitude']  + (i * dlat)
      np['longitude'] = ret[-1]['longitude'] + (i * dlon)
      ret.append(np)
      t += period
    ret.append(p)
  track['track'] = ret
  return track

#
# Attempt to crop the track to remove dead periods at the beginning and
# the end
#
def fixup_crop ( track, conf ):
  ret   = []
  b     = 0
  e     = len(track['track'])

  # Find start
  for p in track['track']:
    if 'speed' in p and p['speed'] > conf['min_speed']:
      break
    b += 1

  # Find end
  while e > 0:
    p = track['track'][e-1]
    if 'speed' in p and p['speed'] > conf['min_speed']:
      break
    e -= 1

  # Crop
  track['track'] = track['track'][b:e]
  return track

#
# Search for bad data points
# 

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
