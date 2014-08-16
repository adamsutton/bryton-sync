README
===========

This script is designed to automatically synchronise your Bryton (Rider 40)
device with Strava.

It makes uses of 2 key libraries to do all the clever stuff:
  - https://github.com/hozn/stravalib
  - https://github.com/Pitmairen/bryton-gps-linux

Device Access
-------------

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
