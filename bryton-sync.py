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

# System
import os, sys, time, re, json
import threading, inotifyx, select, datetime, shutil
from optparse      import OptionParser
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, Gdk, Notify

# Path
d = os.path.dirname(sys.argv[0]) or '.'
sys.path.insert(0, d + '/bryton-gps-linux/code')
sys.path.insert(0, d + '/stravalib')
sys.path.insert(0, d + '/python-fitparse')

# Local
from brytongps  import export_fake_garmin, rider40
from device     import DeviceMonitor
from log        import log
from stravasync import Strava
from fit        import fit_activity
from gpx2       import gpx_activity
import track

# ###########################################################################
# Helpers
# ###########################################################################

# For bryton params
class Struct(object):
  def __init__(self, entries):
    self.__dict__.update(entries)

# Daemonise
def daemonise ( cwdir = None, umask = None ):
  
  # First child
  pid = os.fork()
  if ( pid > 0 ): sys.exit(0) # exit parent

  # Initialise environment
  os.setsid()
  if ( cwdir ): os.chdir(cwdir)
  if ( umask ): os.umask(umask)

  # Second child
  pid = os.fork()
  if ( pid > 0 ): sys.exit(0) # exit parent

  # Close std file handler
  sys.stdout.flush()
  sys.stderr.flush()
  t = open('/dev/null', 'r')
  os.dup2(t.fileno(), sys.stdin.fileno())
  t = open('/dev/null', 'w')
  os.dup2(t.fileno(), sys.stdout.fileno())
  os.dup2(t.fileno(), sys.stderr.fileno())

# Fixup a track
def track_fixup ( track, movedist ):
  ret     = []
  first   = False
  ptp     = None
  static  = True
  start   = None
  dist    = 0.0

  # Build to list of data points
  for seg in track:
    for tp, lp in seg:
      if not lp: continue # not likely, faulty point
      if not tp: tp = ptp
      if not tp: continue # no previous point yet

      # Check for lack of movement
      if ptp is not None:
        d = abs(track.haversine(ptp.longitude, ptp.latitude,\
                          tp.longitude, tp.latitude)) * 1000

        # No movement (if not static)
        if not static and d < movedist:
          tp = ptp
          if lp.cadence is not None:
            lp.cadence = 0
          if lp.speed is not None:
            lp.speed = 0

        # Moving
        elif d > movedist:
          static = False

      # Record last point
      t   = 0.0
      if ptp is not None:
        t   = tp.timestamp - ptp.timestamp
      ptp = tp

      # Ignore until valid first point
      if lp.speed < 2.0 and lp.cadence < 10 and not first:
        continue
      first = True
      start = lp.timestamp

      # Distance (for static trainer)
      dist += (lp.speed * t) / 3600.0

      # Create data point
      d = {
        'timestamp'   : lp.timestamp,
        'latitude'    : tp.latitude,
        'longitude'   : tp.longitude,
        'altitude'    : tp.elevation,
      }
      if lp.temperature is not None:
        d['temperature'] = lp.temperature
      if lp.heartrate is not None:
        d['heartrate']   = lp.heartrate
      if lp.cadence is not None:
        d['cadence']     = lp.cadence
      if lp.speed is not None:
        d['speed']       = lp.speed
        if static:
          d['distance']  = dist
      ret.append(d)

  return {'static': static, 'timestamp': start, 'track': ret}

# Check if track exists on strava
def on_strava ( strava, beg, end ):

  # Find all tracks from beg
  dt = datetime.datetime.fromtimestamp(beg - 60.0)
  aa = strava.get_activities(beg=dt, limit=1)

  # No activities (so not there)
  if not aa: return False

  # Do the activities overlap
  for a in aa:
    b = time.mktime(a.start_date.timetuple())
    e = time.mktime((a.start_date + a.elapsed_time).timetuple())

    # Match
    if b >= beg and b <= end: return True
    if e >= beg and e <= end: return True

  return False
  
# ###########################################################################
# Class
# ###########################################################################

class BrytonSync ( threading.Thread ):

  # Initialise
  def __init__ ( self, conf ):
    threading.Thread.__init__(self, name='BrytonSync')
    self._run  = False
    self._conf = conf
    self._id   = None
    self._wd   = None
    
    # Initialise device monitor
    self._devmon = DeviceMonitor(conf, self.device_add, self.device_rem)

    # Strava connection
    self._strava  = Strava(conf)

    # Libnotify
    Notify.init('bryton-sync')

    # StatusIcon
    self._statusicon = Gtk.StatusIcon()
    self._statusicon.set_from_file('images/brytonsport.png')
    self._statusicon.set_title('BrytonSync')
    self._statusicon.connect('popup-menu', self.show_status_menu)

    # Status menu
    #about = Gtk.MenuItem(label="About")
    quit  = Gtk.MenuItem(label="Quit")
    quit.connect('activate', self.quit)
    self._statusmenu = Gtk.Menu()
    #self._statusmenu.append(about)
    self._statusmenu.append(quit)

  def quit ( self, x ):
    self.stop()
    Gtk.main_quit()
  
  def show_status_menu ( self, icon, button, time ):
    self._statusmenu.show_all()
    self._statusmenu.popup(None, None, None, None, button, time)

  # Notify
  def notify ( self, title, msg, timeout = 2.0 ):
    n = Notify.Notification.new(title, msg)
    #n.set_data(title, msg)
    n.set_timeout(timeout * 1000)
    n.show()
  
  # Device connected
  def device_add ( self, dev ):
    tdir = os.path.expanduser(self._conf['track_dir'])

    # Log
    prod = dev.get_product()
    ser  = dev.get_serial()
    log('device[%s] added (serial=%s)' % (prod, ser))
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
      n = ts + '.track'
      p = os.path.join(tdir, n)
      if os.path.exists(p): continue

      # Log
      ts = time.strftime('%F %T', tm)
      log('device[%s]: track found %s' % (prod, ts))
      self.notify('Track', 'Start: %s' % ts)
    
      # Create directory
      if not os.path.exists(tdir):
        os.makedirs(tdir)

      # Get track data (from device)
      t = track.convert(h.merged_segments(True))
      t = track.fixup(t, self._conf)
      
      # Save in JSON format
      open(p, 'w').write(json.dumps(t))
      log('device[%s]: track cached' % (prod))
      
  # Device removed
  def device_rem ( self, dev ):
    prod = dev.get_product()
    ser  = dev.get_serial()
    log('device removed (%s, %s)' % (prod, ser))
    self.notify('Device Removed', 'Device: %s\nSerial: %s' % (prod, ser))

  # Start file monitor
  def start ( self ):
    self.notify('Started', 'BrytonSync started')
    if self._run: return

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
    if not self._conf['nosync']: threading.Thread.start(self)

  # Stop
  def stop ( self ):
    if not self._run: return
    self._run = False
    inotifyx.rm_watch(self._id, self._wd)
    self._id  = None
    self._wd  = None
    self._devmon.stop()
  
  # File added
  def added ( self, tpath ):
    try:
      sdir = os.path.expanduser(self._conf['strava_dir'])
  
      # Create directory
      if not os.path.exists(sdir):
        os.makedirs(sdir)
      
      # Ignore invalid types
      if not tpath.endswith('.track'):
        return True

      # Ignore already synced
      spath = os.path.join(sdir, os.path.basename(tpath))
      if os.path.exists(spath):
        return True

      # Load the track
      track = json.loads(open(tpath).read())
      beg   = track['track'][0]['timestamp']
      end   = track['track'][-1]['timestamp']
      log('sync: new track found %s' %\
          time.strftime('%F %T', time.gmtime(beg)))

      # See if this is already on strava (from somewhere else)
      if not self._conf['nosend'] and on_strava(self._strava, beg, end):
        log('sync: already found on strava')
        open(spath, 'w')
        return True

      # Create appropriate format
      ext  = self._conf['format']
      path = '/tmp/bryton.' + ext
      if ext == 'fit':
        t = fit_activity(track['track'], track['static'])
      elif ext == 'gpx':
        t = gpx_activity(track['track'], track['static'])
      else:
        return True
      open(path, 'w').write(t)

      # Send to strava
      log('syncing %s'%  os.path.basename(tpath))
      ok = False
      if self._conf['nosend']:
        log('  fake send')
        ok = True
      elif self._strava.send_activity(path, ext):
        self.notify('Track', 'Uploaded : %s' % tpath)
        log('  sent')
        ok = True
      else:
        log('  failed')
        # Will potentially try again next time

      if ok:
        shutil.move(path, spath)

      return True

    except Exception, e:
      import traceback
      traceback.print_exc(e)
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

    'min_distance'  : 2.0,  # km
    'min_time'      : 300,  # sec
    'min_speed'     : 15.0, # km/h

    'move_distance' : 5.0, # metres (1.25/sec)

    'update_period' : 1.0, # 1Hz

    'oldest'        : 5, # days

    'track_dir'     : '~/.bryton/tracks',
    'strava_dir'    : '~/.bryton/strava',

    'client_id'     : 2550,
    'client_secret' : '8878e1ad87a1c0f9581a482bdb45a3bc10af7ff2',
    'client_url'    : 'https://home.adamsutton.me.uk/brytonsync/auth_callback',

    'cookiepath'    : '~/.bryton/cookies.txt',

    'format'        : 'fit',

    'nosync'        : False,
    'nosend'        : False,
  }

  # Parse command line
  optp = OptionParser()
  optp.add_option('-c', '--conf', default='~/.brytonrc',
                  help='Specify path to configuration file')
  optp.add_option('-o', '--options', default=[], action='append')
  optp.add_option('-f', '--fork', default=False, action='store_true',
                  help='Fork into the background')
  optp.add_option('--nosync', default=False, action='store_true',
                  help='Do not sync tracks to strava')
  optp.add_option('--nosend', default=False, action='store_true',
                  help='Fake the sync, but do not actually send')
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

  if opts.nosync: conf['nosync'] = True
  if opts.nosend: conf['nosend'] = True

  # Fork
  if opts.fork: daemonise()

  # Start
  b = BrytonSync(conf)
  b.start()

  # Start GTK main thread
  import signal
  signal.signal(signal.SIGINT, signal.SIG_DFL)
  Gdk.threads_init()

  # Turn into daemon
  Gtk.main()

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
