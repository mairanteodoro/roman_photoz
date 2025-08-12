### COSMOS example with rail+lephare ###

import argparse
import os
from collections import OrderedDict
from pathlib import Path
from importlib import resources

import lephare as lp
import numpy as np
from astropy.table import Table
from numpy.lib import recfunctions as rfn
from rail.core.stage import RailStage

from roman_photoz import create_roman_filters
from roman_photoz.default_config_file import default_roman_config
from roman_photoz.logger import logger
from roman_photoz.utils import save_catalog, get_roman_filter_list
import re
import astropy.units as u
import math

ROMAN_DEFAULT_CONFIG = default_roman_config

DS = RailStage.data_store
DS.__class__.allow_overwrite = True

LEPHAREDIR = os.environ.get("LEPHAREDIR", lp.LEPHAREDIR)
LEPHAREWORK = os.environ.get(
    "LEPHAREWORK", (Path(LEPHAREDIR).parent / "work").as_posix()
)
CWD = os.getcwd()
DEFAULT_OUTPUT_CATALOG_FILENAME = "roman_simulated_catalog.parquet"


class SimulatedCatalog:
    """
    A class to create a simulated catalog using the Roman telescope data.

    Attributes
    ----------
    data : OrderedDict
        A dictionary to store the data.
    lephare_config : dict
        Configuration for LePhare.
    flux_cols : list
        List of flux columns.
    flux_err_cols : list
        List of flux error columns.
    inform_stage : None
        Placeholder for inform stage.
    estimated : None
        Holds all the results from `roman_photoz`.
    filter_lib : None
        Placeholder for filter library.
    simulated_data_filename : str
        Filename for the simulated data.
    simulated_data : None
        Placeholder for simulated data.
    """

    def __init__(self, nobj: int = 1000, mag_noise: float = 0.1):
        """
        Initializes the SimulatedCatalog class.
        """
        self.data = OrderedDict()
        self.lephare_config = ROMAN_DEFAULT_CONFIG
        self.nobj = nobj
        self.flux_cols = []
        self.flux_err_cols = []
        self.inform_stage = None
        self.estimated = None
        self.simulated_data_filename = ""
        self.filter_lib = None
        self.simulated_data = None
        self.roman_catalog_template = self.read_roman_template_catalog()
        self.filter_list = get_roman_filter_list()
        self.mag_noise = mag_noise

    def create_column_names(self):
        colnames_list = []
        for colname in self.roman_catalog_template.dtype.names:
            for filter_id in self.filter_list:
                # make sure we replace any column name that contains the filter_id
                if filter_id in colname:
                    colname = colname.replace(filter_id, "{}")
                    break
            colnames_list.append(colname)

        # colnames = [x.format(y) for y in self.filter_list for x in colnames_list]

        return list(
            dict.fromkeys(colnames_list)
        )  # remove duplicates while preserving order

    def read_roman_template_catalog(self):
        input_filename = "roman_catalog_template.parquet"
        input_path = resources.files("roman_photoz.data").joinpath(input_filename)
        template = Table.read(input_path, format="parquet")
        empty_template = Table(dtype=template.dtype)
        return empty_template

    def is_folder_not_empty(self, folder_path: str, partial_text: str) -> bool:
        """
        Check if a folder exists and contains files with the specified partial text.

        Parameters
        ----------
        folder_path : str
            The path to the folder.
        partial_text : str
            The partial text to look for in filenames.

        Returns
        -------
        bool
            True if the folder exists and contains files with the partial text, False otherwise.
        """
        path = Path(folder_path)
        if path.exists() and path.is_dir():
            if any(path.glob(f"*{partial_text}*")):
                return True
        return False

    def create_filter_files(self):
        """
        Create filter files for the Roman telescope.

        This method checks if the required filter files are present in the specified directory.
        If not, it generates them using the `create_roman_filters` module.

        Raises
        ------
        FileNotFoundError
            If the filter files cannot be created or found.
        """
        filter_files_present = self.is_folder_not_empty(
            Path(self.lephare_config["FILTER_REP"], "roman"), "roman_"
        )
        if not filter_files_present:
            logger.info("Filter files not found, generating them...")
            create_roman_filters.run()

        logger.info(
                f"Using filter library in {self.lephare_config['FILTER_REP']}/roman."
        )

    def create_simulated_data(self):
        """
        Generate simulated data using the LePhare configuration.

        This method prepares the LePhare environment and generates simulated data
        for galaxies, stars, and quasars based on the provided configuration.

        Raises
        ------
        RuntimeError
            If the LePhare preparation fails or the configuration is invalid.
        """

        fname = self.lephare_config['GAL_LIB_OUT']
        catalog_name = Path(
            LEPHAREWORK, "lib_mag", f"{fname}.dat"
        ).as_posix()
        if os.path.exists(catalog_name):
            logger.info('LePhare synthetic magnitudes already exist, skipping creation.')
            return

        star_overrides = {}
        qso_overrides = {
            "MOD_EXTINC": "0,1000",
            "EB_V": "0.,0.1,0.2,0.3",
            "EXTINC_LAW": "SB_calzetti.dat",
        }
        gal_overrides = {
            "GAL_SED": f"{LEPHAREDIR}/examples/COSMOS_MOD.list",
            "LIB_ASCII": "YES",
        }

        logger.info("Preparing LePhare environment for simulated data generation...")
        lp.prepare(
            config=self.lephare_config,
            star_config=star_overrides,
            gal_config=gal_overrides,
            qso_config=qso_overrides,
        )

        self.simulated_data_filename = gal_overrides.get("GAL_LIB_OUT")
        logger.info("Simulated data generated successfully")

    def create_simulated_input_catalog(
        self,
        output_filename: str = DEFAULT_OUTPUT_CATALOG_FILENAME,
        output_path: str = "",
    ):
        """
        Create a simulated input catalog from the simulated data.

        + read the ROMAN_SIMULATED_MAGS.dat produced by LePhare's
            `prepare` method in `create_simulated_input_catalog`. The
            columns name are defined by LePhare.

        + format the columns name to match Roman catalog's specifications

        """
        fname = self.lephare_config['GAL_LIB_OUT']
        catalog_name = Path(
            LEPHAREWORK, "lib_mag", f"{fname}.dat"
        ).as_posix()
        colnames = self.create_header(catalog_name=catalog_name)

        # some columns are actually integers, e.g., model, ext_law, N_filt
        # but treating these as floats doesn't really hurt anything; we are
        # using these to generate a romancal catalog parquet output file
        # that doesn't contain these columns anyway
        self.simulated_data = np.loadtxt(
            catalog_name, dtype=[(n, 'f4') for n in colnames], encoding="utf-8"
        )
        self.simulated_data = self.simulated_data[self.simulated_data['redshift'] > 0]

        # we're keeping only the columns with magnitude and true redshift information
        cols_to_keep = [
            name
            for name in self.simulated_data.dtype.names
            if "mag" in name or "redshift" in name
        ]

        # we're matching the number of objects in the template
        num_lines = self.nobj
        random_lines = self.pick_random_lines(num_lines)
        catalog = random_lines[cols_to_keep]

        final_catalog = self.add_error(catalog, mag_noise=self.mag_noise)
        final_catalog = self.add_ids(final_catalog)

        redshift = final_catalog["redshift"]

        final_catalog = rfn.append_fields(
            final_catalog, "redshift_true", redshift, usemask=False
        )
        # remove the redshift column
        final_catalog = rfn.drop_fields(final_catalog, ["redshift"])

        final_catalog = self.create_simulated_roman_catalog(final_catalog)

        final_catalog = Table(final_catalog)

        save_catalog(
            final_catalog,
            output_filename=output_filename,
            output_path=output_path,
            overwrite=True,
        )

    def abmag_to_njy(self, abmag):
        # convert AB magnitude to flux density in nJy
        return (abmag * u.ABmag).to(u.nJy)

    def create_simulated_roman_catalog(self, catalog):
        """
        Update the Roman catalog template with the simulated data.

        Parameters
        ----------
        catalog : np.ndarray
            The catalog data to update the Roman catalog template with.
        """
        filter_list = self.filter_list

        # in the asdf template file we only have the flux in
        # the F158 filter so we're adding the other filters
        colnames = self.create_column_names()

        # determine what filters are available in the template catalog
        available_filters = list(
            set(re.findall(r"f\d+", " ".join(self.roman_catalog_template.dtype.names)))
        )
        # use the first available filter as the default (regardless of which one it is)
        default_filter = available_filters[0]

        # create an empty table to hold the simulated data for the Roman catalog
        simulated_roman_catalog = Table()
        for field in self.roman_catalog_template.dtype.names:
            simulated_roman_catalog[field] = np.zeros(
                len(catalog), dtype=self.roman_catalog_template.dtype[field])

        simulated_roman_catalog['label'] = catalog['label']

        # then add the simulated data
        for filter_name in filter_list:
            for colname in colnames:
                colname = colname.format(filter_name)
                if "flux_err" in colname:
                    # flux error = ln(10) / 2.5 mag_error
                    flux = self.abmag_to_njy(catalog[f'magnitude{filter_name}'])
                    errname = f'magnitude{filter_name}_err'
                    if errname in catalog.dtype.names:
                        simulated_value = (
                            np.log(10) / 2.5 * flux * catalog[errname])
                    else:
                        simulated_value = 0.01 * flux
                elif "flux" in colname:
                    simulated_value = self.abmag_to_njy(
                        catalog[f"magnitude{filter_name}"])
                else:
                    continue
                simulated_roman_catalog[colname] = simulated_value

        simulated_roman_catalog['redshift_true'] = catalog['redshift_true']

        return simulated_roman_catalog

    def add_ids(self, catalog):
        """
        Add an ID column to the catalog.

        Parameters
        ----------
        catalog : np.ndarray
            The catalog data.

        Returns
        -------
        np.ndarray
            The catalog data with an ID column added.
        """
        ids = np.arange(1, len(catalog) + 1)
        catalog = rfn.append_fields(catalog, "label", ids, usemask=False)

        new_dtype = [("label", catalog["label"].dtype)] + [
            (name, catalog[name].dtype)
            for name in catalog.dtype.names
            if name != "label"
        ]
        new_catalog = np.empty(catalog.shape, dtype=new_dtype)
        for name in new_catalog.dtype.names:
            new_catalog[name] = catalog[name]

        return new_catalog

    def add_error(self, catalog, mag_noise: float = 0.1, seed: int = 42):
        """
        Add a Gaussian error to each magnitude column in the catalog.

        For each magnitude column, this method adds:
        + a Gaussian noise with a mean equal to the original value and a standard deviation of `mag_noise`
        + an error column (`<magnitude_column>_err`) with values set to `mag_noise`.

        Parameters
        ----------
        catalog : np.ndarray
            The catalog data.
        mag_noise : float, optional
            The standard deviation of the Gaussian noise to be added to the observed magnitudes (default: 0.1).
        seed : int, optional
            The seed for the random number generator.

        Returns
        -------
        np.ndarray
            The catalog data with error columns added.
        """
        # don't do anything if we're not adding noise
        if mag_noise <= 0:
            logger.info('Not adding noise to the catalog.')
            return catalog

        new_dtype = []
        for col in catalog.dtype.names:
            new_dtype.append((col, catalog[col].dtype))
            if "mag" in col:
                new_dtype.append((f"{col}_err", catalog[col].dtype))

        new_catalog = np.zeros(catalog.shape, dtype=new_dtype)
        rng = np.random.default_rng(seed=seed)
        for col in catalog.dtype.names:
            # add some noise to the magnitudes
            new_catalog[col] = rng.normal(
                loc=catalog[col], scale=mag_noise, size=catalog[col].shape
            )
            if "mag" in col:
                # add error
                new_catalog[f"{col}_err"] = mag_noise

        return new_catalog

    def create_header(self, catalog_name: str):
        """
        Create the header for the catalog.

        Parameters
        ----------
        catalog_name : str
            The name of the catalog file.

        Returns
        -------
        list
            The list of column names for the catalog.
        """
        with open(catalog_name) as f:
            # BEWARE of the format of LEPHAREWORK/lib_mag/*_COSMOS.dat!
            # ignore the first N_filt lines in the file
            for _ in range(len(self.filter_list) + 1):
                next(f)
            colname_list = f.readline().strip().split(" ")
        colnames = [x for x in colname_list if "[N_filt]" not in x]
        colvector = [x for x in colname_list if "[N_filt]" in x]
        expanded_colvector = [
            x.replace("[N_filt]", filter_name)
            for x in colvector
            for filter_name in self.filter_list
        ]
        colnames.extend(expanded_colvector)

        colnames = [x for x in colnames if "#" not in x]
        return colnames

    def pick_random_lines(self, num_lines: int):
        """
        Pick random lines from the data array.

        Parameters
        ----------
        num_lines : int
            The number of random lines to pick.

        Returns
        -------
        np.ndarray
            An array containing the randomly picked lines.
        """
        if num_lines > 0:
            if self.simulated_data is None:
                raise ValueError(
                    "Data array is not initialized. Please run create_simulated_input_catalog first."
                )

            total_lines = len(self.simulated_data)
            if num_lines > total_lines:
                raise ValueError(
                    f"Requested {num_lines} lines, but only {total_lines} lines are available."
                )

            rng = np.random.default_rng()
            random_indices = rng.choice(total_lines, num_lines, replace=False)
            return self.simulated_data[random_indices]
        else:
            return self.simulated_data

    def process(
        self,
        output_path: str = "",
        output_filename: str = DEFAULT_OUTPUT_CATALOG_FILENAME,
    ):
        """
        Run the process to create the simulated catalog.
        """
        self.create_filter_files()
        self.create_simulated_data()
        self.create_simulated_input_catalog(
            output_filename=output_filename, output_path=output_path,
        )

        logger.info("DONE")


def main():
    def parse_args():
        parser = argparse.ArgumentParser(
            description="Create a simulated catalog using the Roman telescope data."
        )
        parser.add_argument(
            "--output-path",
            type=str,
            default=LEPHAREWORK,
            help="Path to save the output catalog.",
        )
        parser.add_argument(
            "--output-filename",
            type=str,
            default=DEFAULT_OUTPUT_CATALOG_FILENAME,
            help="Filename for the output catalog.",
        )
        parser.add_argument(
            "--nobj",
            type=int,
            default=-1,
            help="Number of objects to create.",
        )
        parser.add_argument(
            '--mag-noise', type=float, default=0,
            help='Add noise to the measurements.'
        )

        return parser.parse_args()

    args = parse_args()

    logger.info("Starting simulated catalog creation...")
    rcp = SimulatedCatalog(args.nobj, mag_noise=args.mag_noise)
    rcp.process(args.output_path, args.output_filename)
    logger.info("Simulated catalog creation completed successfully")


if __name__ == "__main__":
    main()
