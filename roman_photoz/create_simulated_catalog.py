### COSMOS example with rail+lephare ###

import argparse
import os
from collections import OrderedDict
from pathlib import Path

import lephare as lp
import numpy as np
from astropy.table import Table
from numpy.lib import recfunctions as rfn
from rail.core.stage import RailStage

from roman_photoz import create_roman_filters
from roman_photoz.default_config_file import default_roman_config
from roman_photoz.logger import logger
from roman_photoz.utils import save_catalog, get_roman_filter_list

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
    nobj : int
        Maximum number of objects to process from input catalog.
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

    def __init__(self, include_errors: bool = False):
        """
        Initializes the SimulatedCatalog class.
        """
        self.data = OrderedDict()
        self.lephare_config = ROMAN_DEFAULT_CONFIG
        self.nobj = 100
        self.flux_cols = []
        self.flux_err_cols = []
        self.inform_stage = None
        self.estimated = None
        self.simulated_data_filename = ""
        self.simulated_data = None
        self.include_errors = include_errors

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
            f"Created filter library using the filter files in {self.lephare_config['FILTER_REP']}/roman."
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
        star_overrides = {}
        qso_overrides = {}
        gal_overrides = {
            "GAL_LIB_IN": "LIB_CE",
            "GAL_LIB_OUT": "ROMAN_SIMULATED_MAGS",
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
        catalog_name = Path(
            LEPHAREWORK, "lib_mag", f"{self.simulated_data_filename}.dat"
        ).as_posix()
        colnames = self.create_header(catalog_name=catalog_name)

        self.simulated_data = np.genfromtxt(
            catalog_name, dtype=None, names=colnames, encoding="utf-8"
        )

        # we're keeping only the columns with magnitude and true redshift information
        cols_to_keep = [
            name
            for name in self.simulated_data.dtype.names
            if "mag" in name or "redshift" in name
        ]

        # we're matching the number of objects in the template
        num_lines = -1  # len(self.roman_catalog_template)
        random_lines = self.pick_random_lines(num_lines)
        catalog = random_lines[cols_to_keep]

        final_catalog = self.add_error(catalog)
        final_catalog = self.add_ids(final_catalog)

        context = np.full((len(catalog)), 0)
        # zspec = np.full((num_lines), np.nan)
        zspec = final_catalog["redshift"]
        string_data = final_catalog["redshift"]

        final_catalog = rfn.append_fields(
            final_catalog, "context", context, usemask=False
        )
        final_catalog = rfn.append_fields(final_catalog, "zspec", zspec, usemask=False)
        final_catalog = rfn.append_fields(
            final_catalog, "z_true", string_data, usemask=False
        )
        # remove the redshift column
        final_catalog = rfn.drop_fields(final_catalog, ["redshift"])

        final_catalog = Table(final_catalog)

        save_catalog(
            final_catalog,
            output_filename=output_filename,
            output_path=output_path,
            overwrite=True,
        )

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

    def add_error(
        self, catalog, mag_noise: float = 0.1, mag_err: float = 0.01, seed: int = 42
    ):
        """
        Add a Gaussian error to each magnitude column in the catalog.

        For each magnitude column, this method adds:

        + a Gaussian noise with a mean equal to the original value and a standard deviation of `mag_noise`

        + an error column (`<magnitude_column>_err`) with values sampled from a Gaussian distribution with a mean of 0 and a standard deviation of `mag_err`.

        Parameters
        ----------
        catalog : np.ndarray
            The catalog data.
        mag_noise : float, optional
            The standard deviation of the Gaussian noise to be added to the observed magnitudes (default: 0.1).
        mag_err : float, optional
            The standard deviation of the Gaussian noise to be added to the error columns (default: 0.01).
        seed : int, optional
            The seed for the random number generator.

        Returns
        -------
        np.ndarray
            The catalog data with error columns added.
        """
        if not self.include_errors:
            logger.info("Skipping error addition to the simulated catalog.")
            return catalog

        rng = np.random.default_rng(seed=seed)
        new_dtype = []
        for col in catalog.dtype.names:
            new_dtype.append((col, catalog[col].dtype))
            if "mag" in col:
                new_dtype.append((f"{col}_err", catalog[col].dtype))

        new_catalog = np.empty(catalog.shape, dtype=new_dtype)
        for col in catalog.dtype.names:
            # add some noise to the magnitudes
            new_catalog[col] = rng.normal(
                loc=catalog[col], scale=mag_noise, size=catalog[col].shape
            )
            if "mag" in col:
                # add error
                new_catalog[f"{col}_err"] = np.abs(
                    rng.normal(loc=0, scale=mag_err, size=catalog[col].shape)
                )

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
        filter_list = get_roman_filter_list()
        with open(catalog_name) as f:
            # BEWARE of the format of LAPHEREWORK/lib_mag/ROMAN_SIMULATED_MAGS.dat!
            # ignore the first N_filt lines in the file
            # for _ in range(len(filter_list) + 1):
            #     next(f)
            colname_list = f.readline().strip().split(" ")
        colnames = [x for x in colname_list if "vector" not in x]
        colvector = [x for x in colname_list if "vector" in x]
        expanded_colvector = [
            x.replace("vector", filter_name)
            for x in colvector
            for filter_name in filter_list
        ]
        colnames.extend(expanded_colvector)

        colnames = [x for x in colnames if "#" not in x]
        colnames = [x for x in colnames if "age" not in x]
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
            output_filename=output_filename,
            output_path=output_path,
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
            "--add-error",
            action="store_true",
            help="Optionally add error to the simulated catalog.",
        )
        return parser.parse_args()

    args = parse_args()

    logger.info("Starting simulated catalog creation...")
    rcp = SimulatedCatalog(include_errors=args.add_error)
    rcp.process(args.output_path, args.output_filename)
    logger.info("Simulated catalog creation completed successfully")

    logger.info("Done.")


if __name__ == "__main__":
    main()
