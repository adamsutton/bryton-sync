#!/usr/bin/env python
#
# stravasync.py - Strava Access
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
import urlparse
import gi
gi.require_version('WebKit', '3.0')
from gi.repository import Gtk, Gdk, WebKit, Soup

# Local
import stravalib
from log import log

class Strava:

  # Initialise
  def __init__ ( self, conf ):
    cid  = conf['client_id']
    curl = conf['client_url']

    self._conf    = conf
    self._client  = stravalib.Client()
    self._web     = WebKit.WebView()
    self._win     = Gtk.Window()
    self._authurl = self._client.authorization_url(client_id=cid,
                                                   redirect_uri=curl,
                                                   scope='write')

    # Auth condition
    self._authcv  = threading.Condition()

    # Cookie processing
    cpath     = os.path.expanduser(self._conf['cookiepath'])
    cookiejar = Soup.CookieJarText.new(cpath, False)
    cookiejar.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)
    session = WebKit.get_default_session()
    session.add_feature(cookiejar)

    # Setup Webkit callbacks
    self._web.connect('load-committed', self.load_start)
    self._web.connect('load-error',      self.load_error)

    # Setup Web Window
    self._win.set_title('Strava Authentication')
    self._win.set_default_size(800, 600)

    # Add browser
    sw  = Gtk.ScrolledWindow()
    sw.add(self._web)
    self._win.add(sw)

    # Event handlers
    self._win.connect('delete-event', Gtk.main_quit)

    # Hack (for some reason, not opening something here causes
    # things to crash)
    self._win.show_all()
    self._web.open('http://strava.com')
    self._win.hide()

  # Error
  def load_error ( self, web, frame, a, b ):
    print 'ERROR: %s %s' % (a, b)
    pass

  # Callback on page load
  def load_start ( self, web, frame ):
    uri = frame.get_uri()
    print uri

    # Authenticated
    if uri.startswith(self._conf['client_url']):
      log('authenticated')
      self._win.hide()
      self._authtoken = None
      
      # Parse URL
      parse  = urlparse.urlparse(uri)
      params = urlparse.parse_qs(parse.query)
      code   = params['code'][0]

      # Get Token
      cid             = self._conf['client_id']
      csec            = self._conf['client_secret']
      self._authtoken = self._client.exchange_code_for_token(client_id=cid,
                                                             client_secret=csec,
                                                             code=code)
      # Done
      self._authcv.acquire()
      self._authcv.notify()
      self._authcv.release()

    # Not authenticated
    elif 'strava.com/login' in uri or 'strava.com/oauth' in uri:
      log('showing strava login window')
      self._win.show_all()
      return


  # Perform authentication
  #
  def _authenticate ( self ):

    # Open auth url
    Gdk.threads_enter()
    self._web.open(self._authurl)
    Gdk.threads_leave()

    # Wait
    self._authcv.acquire()
    self._authcv.wait()
    self._authcv.release()
    if not self._authtoken:
      return False
    log('authenticated %s' % self._authtoken)
    return True
    
  #
  # Authenticate
  #
  def authenticate ( self ):

    # Check if already authenticated
    try:
      self._client.get_athlete()
      #log('already authenticated')
    except Exception, e:
      try:
        if not self._authenticate():
          return False
      except:
        return False

    return True

  #
  # Send activity
  #
  def send_activity ( self, path, type ):

    # Authenticate
    if not self.authenticate():
      return False

    # Send Activity
    try:
      self._client.upload_activity(open(path), type)
      log('activity submitted')
      return True
    except Exception, e:
      import traceback
      traceback.print_exc(e)
      log('failed to upload [e=%s]' % e)
  
    return False
  
  #
  # Send TCX
  #
  def send_tcx ( self, path ):
    return self.send_activity(path, 'tcx')

  #
  # Send FIT
  #
  def send_fit ( self, path ):
    return self.send_activity(path, 'fit')


# ###########################################################################
# Testing
# ###########################################################################
  

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
