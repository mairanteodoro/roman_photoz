# Summary

`simulate_and_process_l1_files.sh` provides a reproducible workflow for
simulating and processing Roman telescope L1 files, integrating catalog
creation, photometric simulation, image generation, association file
preparation, and cataloging steps.

---

# Detailed Description of `simulate_and_process_l1_files.sh`

This script automates the end-to-end simulation and processing of Roman
telescope Level 1 (L1) files for one SCA (01) and all the filters. It executes
a series of steps to generate input catalogs, simulate photometry, update
catalogs with fluxes, create images, and run multiple association and cataloging
pipelines. Below is a step-by-step breakdown:

## 1. Create Romanisim Input Catalog

- **Command:** `python -m make_romanisim_input_catalog`
- **Description:** Generates an initial catalog of galaxies for Romanisim
  simulations. The output is in maggies and serves as the base for all subsequent
  steps.

## 2. Simulate Photometry Catalog

- **Command:** `python -m roman_photoz.create_simulated_catalog --output-path .`
- **Description:** Produces a simulated photometric catalog using COSMOS
  templates and the lephare.prepare method. No extra photometric errors are added.

## 3. Update Romanisim Catalog with Simulated Fluxes

- **Command:** `python -m update_romanisim_catalog_fluxes --target-catalog
romanisim_input_catalog.ecsv --flux-catalog roman_simulated_catalog.parquet
--output-filename romanisim_input_catalog_fluxes_updated.ecsv`
- **Description:** Updates the Romanisim input catalog with fluxes from the
  simulated photometry catalog, preparing it for image simulation.

## 4. Generate Simulated Images

- **Command:** `./run_romanisim.sh F062 F087 F106 F129 F158 F184 F213
- **Description:** Runs Romanisim to generate simulated images for all specified
  filters using the updated catalog.

## 5. Create Association Files for ELP and Run ELP

- **Commands:** `./create_asn_files_for_elp.sh F062 F087 F106 F129 F158 F184 F213`
  `./run_elp.sh *_uncal.json`
- **Description:** Prepares association files for the ELP pipeline for each
  filter and executes the ELP pipeline.

## 6. Create Association Files for Skycells

- **Command:** `./create_skycell_asn.sh F062 F087 F106 F129 F158 F184 F213
- **Description:** Generates association files for skycell-based processing for
  all filters.

## 7. Run MOS Pipeline

- **Command:** `./run_mos.sh r00001_p_*asn.json`
- **Description:** Runs the MOS pipeline for the skycells, using the
  previously generated association files.
  Note: will run 42 simultaneous coadds as written!

## 8. Create Association Files for Multiband Catalog

- **Command:** `./create_asn_for_mbandcatalog.sh *_coadd.asdf`
- **Description:** Prepares association files for multiband catalog generation
  for the selected skycell.

## 9. Run Multiband Catalog Step

- **Command:** `find mbcat_*_wfi01.json | xargs -n1 -P8 -I{} strun romancal.step.MultibandCatalogStep {} --snr_threshold 5`
- **Description:** Executes the MultibandCatalogStep to produce the final
  multiband catalog for the skycell.

## 10. Run roman-photoz

- **Command:** `find 270*_cat.parquet | xargs -I{} -P8 -n1 roman-photoz --input-path . --input-filename {} --output-path . --output-filename {}.photoz.parquet`  # we should update this to put the photoz information in the input multiband catalogs
- **Description:** Runs the Roman Photo-z pipeline on the generated catalog to
  estimate photometric redshifts.

---

## Additional Notes

- The script uses a predefined skycell and a list of filters for all relevant
  steps.
- Each major step is chained with `&&` to ensure the workflow stops on error.
- The script is modular and can be adapted for different skycells or filter sets
  by changing the relevant variables.
