#!/bin/bash

S=$(readlink $0)
[ "x$S" == "x" ] && S=$0
cd $(dirname $S)
./bryton-sync.py 2> /dev/null 1> /tmp/bryton.log &
