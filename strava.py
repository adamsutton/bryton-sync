#!/usr/bin/env python
#
# Simple client to autheticate with strava, next step submit TCX files 
# (when I have some)

import os, sys, time, re
import urlparse
import stravalib
from gi.repository import Gtk, WebKit, Soup

# Strava Client details
CLIENT_ID=2550
CLIENT_SECRET='8878e1ad87a1c0f9581a482bdb45a3bc10af7ff2'
CLIENT_AUTHURL='https://home.adamsutton.me.uk/brytonsync/auth_callback'

# Sync client
class BrytonSync:

  def load_start ( self, web, frame ):
    uri = frame.get_uri()
    if CLIENT_AUTHURL not in uri: return

    # Parse URL
    parse  = urlparse.urlparse(uri)
    params = urlparse.parse_qs(parse.query)

    # Get Token
    token = self.strava.exchange_code_for_token(client_id=CLIENT_ID,\
                                                client_secret=CLIENT_SECRET,\
                                                code=params['code'][0])

    # List activities
    activities = self.strava.get_activities()
    for a in activities:
      print a.name, a.start_date, a.moving_time, a.max_speed, a.distance, a.description
      

    # Hide the window
    self.win.destroy()
    self.web = None
    sys.exit(0)

  def __init__(self):

    # Initialise Strava
    self.strava = stravalib.Client()
    url = self.strava.authorization_url(client_id=CLIENT_ID,\
                                        redirect_uri=CLIENT_AUTHURL)

    # Initialise webkit
    self.web = WebKit.WebView()
    self.web.open(url)
    self.web.connect('load-committed',    self.load_start)
    #self.web.connect('load-error',      self.load_start)

    # Cookies
    cookiejar = Soup.CookieJarText.new("cookies.txt", False)
    cookiejar.set_accept_policy(Soup.CookieJarAcceptPolicy.ALWAYS)
    session = WebKit.get_default_session()
    session.add_feature(cookiejar)

    # Basic window for authentication
    self.win = Gtk.Window()
    self.win.set_title('Strava Authentication')

    # Add browser
    sw  = Gtk.ScrolledWindow()
    sw.add(self.web)
    self.win.add(sw)

    # Event handlers
    self.win.connect('delete-event', Gtk.main_quit)
  
    # Show
    self.win.set_default_size(800, 600)
    self.win.show_all()

if __name__ == '__main__':
  BrytonSync()
  Gtk.main()

