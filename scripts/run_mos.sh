#!/bin/bash

for cal_file in $@; do
  echo "Processing file: $cal_file"
  # spawn background processes for each file
  (
      strun roman_mos "$cal_file" || echo "Failed to process $cal_file"
  ) &
done

wait
