#!/bin/bash

# this skycell was deemed the best one for WFI01
skycell_id="270p65x49y70"
# filter list
filter_list="f062 f087 f106 f129 f158 f184 f213"

# 1 - create romanisim input catalog (the results will be in maggies)
# (romanisim.make_cosmos_galaxies())
python -m make_romanisim_input_catalog &&

  # 2 - create roman_photoz simulated catalog (using COSMOS templates and lephare.prepare method)
  # (roman_photoz.create_simulated_catalog.py -- no additional photometric errors added to the simulated catalog)
  python -m roman_photoz.create_simulated_catalog \
    --output-path . &&

  # 3 - update catalog from step 1 with the fluxes from the catalog from step 2
  # (roman_photoz.update_romanisim_catalog_fluxes.py)
  python -m update_romanisim_catalog_fluxes \
    --target-catalog romanisim_input_catalog.ecsv \
    --flux-catalog roman_simulated_catalog.parquet \
    --output-filename romanisim_input_catalog_fluxes_updated.ecsv &&

  # 4 - run romanisim-make-image on the catalog from step 3
  ./run_romanisim.sh ${filter_list} &&

  # 5 - create association files for ELP and run roman_elp
  ./create_asn_files_for_elp.sh ${filter_list} &&
  ./run_elp.sh &&

  # 6 - create the association files for skycells
  ./create_skycell_asn.sh ${filter_list} &&

  # 7 - create association files for MOS and run roman_mos
  ./run_mos.sh r00001_p_*asn.json &&

  # 8 - create association files for multiband catalog
  ./create_asn_for_mbandcatalog.sh *_coadd.sh &&

  # 9 - run MultibandCatalogStep
  strun romancal.step.MultibandCatalogStep \
    mbcat_${skycell_id}_wfi01.json \
    --deblend True \
    --fit_psf False &&

  # 10 - run roman_photoz
  roman-photoz \
    --input-path . \
    --input-filename r0000101001001001001_0001_wfi01_cat.parquet \
    --output-path . \
    --output-filename result.parquet &&
  echo "All steps completed successfully."
