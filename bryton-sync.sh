#!/bin/bash
cd $(dirname $(readlink $0))
./bryton-sync.py 2> /dev/null 1> /tmp/bryton.log &
