#!/bin/bash

# stop on error
set -e

# filter list
filter_list="f062 f087 f106 f129 f158 f184 f213"

# 1 - create romanisim input catalog (the results will be in maggies)
# (romanisim.make_cosmos_galaxies())
python -m make_romanisim_input_catalog

# 2 - create roman_photoz simulated catalog (using COSMOS templates and lephare.prepare method)
# No additional photometric errors added to the simulated catalog; these will come in during
# the imaging simulations.
python -m roman_photoz.create_simulated_catalog --output-path .

# 3 - update catalog from step 1 with the fluxes from the catalog from step 2
# (roman_photoz.update_romanisim_catalog_fluxes.py)
python -m update_romanisim_catalog_fluxes \
  --target-catalog romanisim_input_catalog.ecsv \
  --flux-catalog roman_simulated_catalog.parquet \
  --output-filename romanisim_input_catalog_fluxes_updated.ecsv

# 4 - run romanisim-make-image on the catalog from step 3
run_romanisim.sh ${filter_list}

# 5 - create association files for ELP and run roman_elp
find *_uncal.asdf | xargs -I{} -P8 -n1 strun roman_elp {}

# 6 - create the association files for skycells
create_skycell_asn.sh ${filter_list}

# 7 - create association files for MOS and run roman_mos
find r00001_p*asn.json | xargs -I{} -P8 -n1 strun roman_mos {}

# 8 - create association files for multiband catalog
create_asn_for_mbandcatalog.sh *_coadd.asdf

# 9 - run MultibandCatalogStep
find mbcat_*_wfi01.json | xargs -I{} -P8 -n1 strun romancal.step.MultibandCatalogStep {} --snr_threshold 10

# 10 - run roman_photoz
# can't run in pxarallel because the files overwrite themselves.
find 270*_cat.parquet | xargs -I{} -P1 -n1 roman-photoz --input-path . --input-filename {} --output-path . --output-filename {}.photoz.parquet
