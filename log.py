#!/usr/bin/env python
#
# log.py - Logging
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
from datetime import datetime

#
# Log stuff
#
def log ( msg ):
  now = datetime.now()
  tm  = now.strftime('%F %T')
  print '%s - %s' % (tm, msg)

# ###########################################################################
# Editor Configuration
#
# vim:sts=2:ts=2:sw=2:et
# ###########################################################################
