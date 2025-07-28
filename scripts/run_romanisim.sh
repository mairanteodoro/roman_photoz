#!/bin/bash

for filter in $@; do
  echo "Processing filter: $filter"
  # spawn background processes for each filter
  romanisim-make-image \
    --radec 270.0 66.0 \
    --level 1 \
    --sca 1 \
    --bandpass "$(echo "$filter" | tr '[:lower:]' '[:upper:]')" \
    --catalog "romanisim_input_catalog_fluxes_updated.ecsv" \
    --stpsf \
    --usecrds \
    --ma_table_number 109 \
    --date 2027-06-01T00:00:00 \
    --rng_seed 1 \
    --drop-extra-dq \
    "r0000101001001001001_0001_{}_{bandpass}_uncal.asdf" &
done

wait
