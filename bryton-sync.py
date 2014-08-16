#!/usr/bin/env python
#
# Simple application to detect plugging in of Bryton Rider 40, extraction
# of data and synchronisation with strava.
#
# The really clever stuff is provided by bryton-gps-linux and stravalib, as
# well as a few other OSS libraries
#

#
# Imports
#

# System
import os, sys, time, re
from datetime import datetime
import simplejson as json
import pynotify

# Local
sys.path.insert(0, 'bryton-gps-linux/code')
import brytongps, device_access

#
# Configuration
#

global CONF
CONF_PATH = os.path.expanduser('~/.bryton/config')
CONF      = {
  'dev_path'      : '/dev/disk/by-id',
  'dev_regex'     : 'BRYTON',

  'min_distance'  : 5.0,
  'min_time'      : 600,

  'track_dir'     : '~/.bryton/tracks',
}

# Load configuration
if os.path.exists(CONF_PATH):
  try:
    c = json.load(CONF_PATH)
    for k in c:
      CONF[k] = c[k]
  except: pass

# Initialise
pynotify.init('bryton-sync')

#
# Command line
#

#
# Utilities
#

def log ( msg ):
  t = datetime.now().strftime('%F %T')
  m = '%s - %s' % (t, msg)
  print m

class Struct(object):
  def __init__(self, entries):
    self.__dict__.update(entries)

#
# Device monitoring
#

def wait_for_device ( detach = False ):
  import inotifyx
  dev = None

  # Build expression
  e   = re.compile(CONF['dev_regex'])

  # Check for device
  def check():
    for d in os.listdir(CONF['dev_path']):
      r = e.search(d)
      if r:
        return os.path.join(CONF['dev_path'], d)

  # Install notify
  fd = inotifyx.init()
  wd = inotifyx.add_watch(fd, CONF['dev_path'],
                          inotifyx.IN_CREATE | inotifyx.IN_DELETE)

  # Wait
  while True:
    dev = check()
    if dev is None and detach: break
    if dev is not None and not detach: break
    ev = inotifyx.get_events(fd)

  # Close
  os.close(fd)
  
  return dev

#
# Main loop
#

while True:

  # Wait for device
  log('waiting for device')
  path = wait_for_device()
  log('device detected')

  # Get device details
  with brytongps.open_device(path) as deva:
    mod,dev = brytongps.get_device(deva)
    ser     = dev.read_serial()
    tdir    = os.path.expanduser(CONF['track_dir'])
    strava  = None

    # Notification
    log('device id %s found' % ser)
    n = pynotify.Notification("Device Ready", ser)
    n.show()
    #time.sleep(2.0)
    n.close()

    # Read tracks
    history = list(reversed(mod.read_history(dev)))
    for h in history:
      if h.summary.distance  < CONF['min_distance']: continue
      if h.summary.ride_time < CONF['min_time']:     continue
  
      # Check if already cached?
      t = time.gmtime(h.summary.start)
      t = time.strftime('%Y%m%d%H%M%S', t)
      n = t + '.tcx'
      p = os.path.join(tdir, n)
      if os.path.exists(p): continue
    
      # Notification
      n = pynotify.Notification('Track', 'Start: %s'% str(h.summary.start))
      n.show()

      # Export track data
      if not os.path.exists(tdir):
        os.makedirs(tdir)
      args = Struct({ 'no_whitespace' : False,
                      'save_to'       : False,
                      'out_name'      : p,
                      'no_laps'       : False})
      brytongps.export_fake_garmin([h], args)

      # Sync to strava

  # Wait until device is gone
  log('waiting for detach')
  wait_for_device(True)
  log('detached')
