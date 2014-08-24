README
===========

This script is designed to automatically synchronise your Bryton (Rider 40)
device with Strava.

It makes uses of 3 key libraries to do all the clever stuff:
  - https://github.com/hozn/stravalib
  - https://github.com/Pitmairen/bryton-gps-linux
  - https://github.com/dtcooper/python-fitparse

It will monitor for Bryton devices, when a device is detected it will extract
the track data (using bryton-gps-linux) and store locally as FIT files 
(using python-fitparse). Finally the files will be automatically uploaded to
Strava (using stravalib).  

I've chosen to use the FIT format, rather than TCX, since it is more expressive
and allows for extra metadata such as temperature (the Bryton Rider 40 includes
a temperature sensor). FIT is also the current default format used by Garmin
Edge devices. The file metadata will list the device as Garmin Edge 500 this is
to ensure that Strava will use the Altimeter readings from the device.

Windows
-------

I do not use Windows, nor do I have any desire to do so! Therefore this script
is Linux only. Should someone wish to add support for Windows, I'm more than
happy to integrate, just don't ask me to test it!

Device Access (Linux)
---------------------

This script needs direct access to the USB device presented when the Bryton
is plugged in. To avoid requiring root priviledges (or permanent sudo) we 
create a new group that will have access to the Bryton device, add yourself
to that group and install a udev rule to change the permissions on insertion.

1. Create bryton group
  $ sudo groupadd -r bryton
2. Add yourself to the group
  $ sudo usermod -a -G bryton $(whoami)
3. Add udev rule
  $ echo 'SUBSYSTEMS=="usb", ATTRS{manufacturer}=="*Bryton*", GROUP="bryton", MODE="0660"' | sudo tee /etc/udev/rules.d/99-bryton.rules
