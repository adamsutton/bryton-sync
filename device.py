#!/usr/bin/env python
#
# device.py - Device Access
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
import select
import threading
import inotifyx

# Local
sys.path.insert(0, 'bryton-gps-linux/code')
from device_access import DeviceAccess
from brytongps     import get_device
from log           import log

# ###########################################################################
# Device Access
# ###########################################################################

#
# Device wrapper
#
class Device:

  def __init__ ( self, mod, dev ):
    self._mod = mod
    self._dev = dev
    self._ser = None

  def get_product ( self ):
    return 'Rider 40'
  
  def get_serial ( self ):
    if not self._ser:
      try:
        self._ser = self._dev.read_serial()
      except:
        return 'Unknown'
    return self._ser

  def get_history ( self ):
    return self._mod.read_history(self._dev)

#
# Class to monitor for valid devices and return handles
#
class DeviceMonitor (threading.Thread):

  # Initialise monitor
  def __init__ ( self, conf, add, rem = None ):
    threading.Thread.__init__(self, name='DevMon')
    self._run  = False
    self._id   = None
    self._wd   = None
    self._conf = conf
    self._add  = add
    self._rem  = rem
    self._dev  = {}

  # Start
  def start ( self ):
    if self._run: return
    self._run = True
    self._id = inotifyx.init()
    self._wd = inotifyx.add_watch(self._id, self._conf['dev_path'],
                                  inotifyx.IN_CREATE | inotifyx.IN_DELETE)
    threading.Thread.start(self)
  
  # Stop
  def stop ( self ):
    if not self._run: return
    self._run = False
    inotifyx.rm_watch(self._id, self._wd)
    os.close(self._id)
    self._id  = None
    self._wd  = None

  # Handle new device
  def added ( self, path ):
    if not os.access(path, os.R_OK | os.W_OK):
      return
    log('device: added %s' % path)
    deva    = DeviceAccess(path)
    deva.open()
    mod,dev = get_device(deva)
    d       = Device(mod, dev)
    self._dev[path] = d
    self._add(d)

  # Removed
  def removed ( self, path ):
    log('device: removed %s' % path)
    if path in self._dev:
      d = self._dev[path]
      if self._rem: self._rem(d)
      del self._dev[path]

  # Check for existing devices
  def scan ( self, path, exp ):
    for f in os.listdir(path):
      r = exp.search(f)
      if r:
        p = os.path.join(path, f)
        self.added(p)

  # Wait for events
  def run ( self ):
    path = self._conf['dev_path']
    exp  = re.compile(self._conf['dev_regex'])
    pd   = select.poll()
    pd.register(self._id, select.POLLIN)
    
    # Run an initial scan
    self.scan(path, exp)
    
    # Wait for events
    while self._run:
      rs = pd.poll(1000)
      if not rs: continue
      for (fd,ev) in rs:
        if fd == self._id and ev & select.POLLIN: 
          try:
            es = inotifyx.get_events(self._id)
            for e in es:
              if not (e.mask & inotifyx.IN_CREATE | inotifyx.IN_DELETE):
                continue
              p = os.path.join(path, e.name)
              if not exp.search(p): continue
              if e.mask & inotifyx.IN_CREATE:
                self.added(p)
              else:
                self.removed(p)
          except: break

# ###########################################################################
# Testing
# ###########################################################################

if __name__ == '__main__':
  CONF      = {
  'dev_path'      : '/dev/disk/by-id',
  'dev_regex'     : 'BRYTON',

  'min_distance'  : 5.0,
  'min_time'      : 600,

  'track_dir'     : '~/.bryton/trac'
  }
  def added ( dev ):
    print dev
  dm = DeviceMonitor(CONF, added)
  dm.start()
  import time
  try:
    while True:
      time.sleep(10.0)
  except: pass
  dm.stop()
  dm.join()

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
