#!/bin/bash

for uncal_file in $@; do
  echo "Processing file: $uncal_file"
  # spawn background processes for each file
  strun roman_elp "$uncal_file" &
done

wait
