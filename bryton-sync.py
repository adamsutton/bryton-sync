##!/usr/bin/env python
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

# System
import os, sys, time, re
import threading, inotifyx, select
from optparse      import OptionParser
from gi.repository import Gtk, Gdk, Notify

# Local
sys.path.insert(0, 'bryton-gps-linux/code')
sys.path.insert(0, 'stravalib')
from brytongps  import export_fake_garmin
from device     import DeviceMonitor
from log        import log
from stravasync import Strava

# ###########################################################################
# Helpers
# ###########################################################################

# For bryton params
class Struct(object):
  def __init__(self, entries):
    self.__dict__.update(entries)

# ###########################################################################
# Class
# ###########################################################################

class BrytonSync ( threading.Thread ):

  # Initialise
  def __init__ ( self, conf ):
    threading.Thread.__init__(self)
    self._run  = False
    self._conf = conf
    self._id   = None
    self._wd   = None
    
    # Initialise device monitor
    self._devmon = DeviceMonitor(conf, self.device_add)

    # Strava connection
    self.strava  = Strava(conf)

    # Libnotify
    Notify.init('bryton-sync')

  # Notify
  def notify ( self, title, msg ):
    pass
    #n = Notify.Notification.new(title, msg)
    #n.set_data(title, msg)
    #n.set_timeout(1.0)
    #n.show()

  # Device connected
  def device_add ( self, dev ):
    tdir = os.path.expanduser(self._conf['track_dir'])

    # Log
    prod = dev.get_product()
    ser  = dev.get_serial()
    log('device added (%s, %s)' % (prod, ser))
    self.notify('Device Added', 'Device: %s\nSerial: %s' % (prod, ser))

    # Read tracks
    history = list(reversed(dev.get_history()))
    for h in history:

      # Ignore short tracks
      if h.summary.distance  < self._conf['min_distance']: continue
      if h.summary.ride_time < self._conf['min_time']:     continue
  
      # Check if already cached?
      tm = time.gmtime(h.summary.start)
      ts = time.strftime('%Y%m%d%H%M%S', tm)
      n = ts + '.tcx'
      p = os.path.join(tdir, n)
      if os.path.exists(p): continue

      # Log
      ts = time.strftime('%F %T', tm)
      log('track found %s' % ts)
      self.notify('Track', 'Start: %s' % ts)
    
      # Export track data
      if not os.path.exists(tdir):
        os.makedirs(tdir)
      args = Struct({ 'no_whitespace' : False,
                      'save_to'       : False,
                      'out_name'      : p,
                      'no_laps'       : False})
      export_fake_garmin([h], args)

  # Start file monitor
  def start ( self ):

    # Create dirs
    tdir = os.path.expanduser(self._conf['track_dir'])
    if not os.path.exists(tdir):
      os.makedirs(tdir)

    # Setup inotify
    self._run = True
    self._id  = inotifyx.init()
    self._wd  = inotifyx.add_watch(self._id, tdir)

    # Start device monitor
    self._devmon.start()
    threading.Thread.start(self)

  # Stop
  def stop ( self ):
    self._run = False
    inotifyx.rm_watch(self._id, self._wd)
    self._id  = None
    self._wd  = None
  
  # File added
  def added ( self, tpath ):
    try:
      sdir = os.path.expanduser(self._conf['strava_dir'])
  
      # Create directory
      if not os.path.exists(sdir):
        os.makedirs(sdir)

      # Ignore already synced
      spath = os.path.join(sdir, os.path.basename(tpath))
      if os.path.exists(spath): return True

      # Send to strava
      log('syncing %s'%  os.path.basename(tpath))
      if self.strava.send_tcx(tpath):
        open(spath, 'w') # create empty file
        return True
    except Exception, e:
      log('error syncing [e=%s]' % e)

    return False

  # Scan
  def scan ( self, tdir ):
    ok = True
    for f in os.listdir(tdir):
      ok = ok and self.added(os.path.join(tdir, f))
    return ok

  # Process files
  def run ( self ):
    scan = False
    tdir = os.path.expanduser(self._conf['track_dir'])

    # Set up poll
    pd   = select.poll()
    pd.register(self._id, select.POLLIN)

    # Scan existing files
    scan = not self.scan(tdir)

    # Wait for events
    while self._run:
      rs = pd.poll(3600000)

      # Force scan
      if scan:
        scan = not self.scan(tdir)
        continue

      # Check for events
      if not rs: continue
      for (fd,ev) in rs:
        if fd == self._id and ev & select.POLLIN:
          es = inotifyx.get_events(self._id)
          for e in es:
            if not (e.mask & inotifyx.IN_CREATE): continue
            p = os.path.join(tdir, e.name)
            if not self.added(p):
              scan = True
    
# ###########################################################################
# Main
# ###########################################################################

# Start
if __name__ == '__main__':

  # Defaults
  conf = {
    'dev_path'      : '/dev/disk/by-id',
    'dev_regex'     : 'BRYTON',

    'min_distance'  : 5.0,
    'min_time'      : 600,

    'track_dir'     : '~/.bryton/tracks',
    'strava_dir'    : '~/.bryton/strava',

    'client_id'     : 2550,
    'client_secret' : '8878e1ad87a1c0f9581a482bdb45a3bc10af7ff2',
    'client_url'    : 'https://home.adamsutton.me.uk/brytonsync/auth_callback',

    'cookiepath'    : '~/.bryton/cookies.txt',
  }

  # Parse command line
  optp = OptionParser()
  optp.add_option('-c', '--conf', default='~/.brytonrc',
                  help='Specify path to configuratiojn file')
  optp.add_option('-o', '--options', default=[], action='append')
  (opts,args) = optp.parse_args()

  # Load configuration
  path = os.path.expanduser(opts.conf)
  if os.path.exists(path):
    try:
      c = json.load(path)
      for k in c:
        conf[k] = c[k]
    except: pass

  # Command overrides
  for o in opts.options:
    p = o.split('=')
    if len(p) != 2: continue
    try:
      p[1] = eval(p[1])
    except: pass
    conf[p[0]] = p[1]

  # Start
  b = BrytonSync(conf)
  b.start()

  # Start GTK main thread
  import signal
  signal.signal(signal.SIGINT, signal.SIG_DFL)
  Gdk.threads_init()
  Gtk.main()

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
