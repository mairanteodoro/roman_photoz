#!/bin/bash

for x in $@; do
  echo "Processing input file: $x"
  skycell_asn r*_"${x}"_cal.asdf -o r00001
done
