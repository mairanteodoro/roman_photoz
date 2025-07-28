#!/bin/bash

skycells=$(printf "%s\n" "$@" | sed -n 's/.*_\([0-9p]*x[0-9]*y[0-9]*\)_f[0-9]*_coadd\.asdf$/\1/p' | sort -u)

for skycell_id in $skycells; do
    echo $skycell_id
    asn_from_list \
	r*_"${skycell_id}"_f*_coadd.asdf \
	-o mbcat_"${skycell_id}"_wfi01.json \
	--product-name $skycell_id
done
