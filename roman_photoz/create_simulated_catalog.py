### COSMOS example with rail+lephare ###

import argparse
import os
from collections import OrderedDict
from pathlib import Path

import lephare as lp
import numpy as np
from numpy.lib import recfunctions as rfn
from rail.core.stage import RailStage
from roman_datamodels import datamodels as rdm

from roman_photoz import create_roman_filters
from roman_photoz.default_config_file import default_roman_config
from roman_photoz.logger import logger

ROMAN_DEFAULT_CONFIG = default_roman_config

DS = RailStage.data_store
DS.__class__.allow_overwrite = True

LEPHAREDIR = os.environ.get("LEPHAREDIR", lp.LEPHAREDIR)
LEPHAREWORK = os.environ.get(
    "LEPHAREWORK", (Path(LEPHAREDIR).parent / "work").as_posix()
)
CWD = os.getcwd()
DEFAULT_OUTPUT_CATALOG_FILENAME = "roman_simulated_catalog.asdf"


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

    def __init__(self):
        """
        Initializes the SimulatedCatalog class.
        """
        self.data = OrderedDict()
        self.lephare_config = ROMAN_DEFAULT_CONFIG
        self.flux_cols = []
        self.flux_err_cols = []
        self.inform_stage = None
        self.estimated = None
        self.filter_lib = None
        self.simulated_data = None
        self.roman_catalog_template = self.read_roman_template_catalog()

    def read_roman_template_catalog(self):
        input_filename = "roman_catalog_template.asdf"
        this_path = Path(__file__).resolve().parent
        input_path = (this_path / "data" / input_filename).as_posix()
        return rdm.open(input_path)

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

    def get_filters(self):
        """
        Retrieve or create filter files for the Roman telescope.

        This method checks if the required filter files are present in the specified directory.
        If not, it generates them using the `create_roman_filters` module. It also initializes
        the filter library using the LePhare configuration.

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

        self.filter_lib = lp.FilterSvc.from_keymap(
            lp.all_types_to_keymap(self.lephare_config)
        )
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
        nobj: int = 100,
    ):
        """
        Create a simulated input catalog from the simulated data.
        """
        fname = self.lephare_config['GAL_LIB_OUT']
        catalog_name = Path(
            LEPHAREWORK, "lib_mag", f"{fname}.dat"
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

        random_lines = self.pick_random_lines(nobj)
        catalog = random_lines[cols_to_keep]

        final_catalog = self.add_error(catalog)
        final_catalog = self.add_ids(final_catalog)

        context = np.full((nobj), 0)
        # zspec = np.full((nobj), np.nan)
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

        self.update_roman_catalog_template(final_catalog)
        # now that self.roman_catalog_template has been updated, we can get rid of
        # the simulated data and the simulated data filename
        del final_catalog

        self.save_catalog(
            output_filename=output_filename,
            output_path=output_path,
        )

    def update_roman_catalog_template(self, catalog):
        """
        Update the Roman catalog template with the simulated data.

        Parameters
        ----------
        catalog : np.ndarray
            The catalog data to update the Roman catalog template with.
        """
        filter_list = (
            default_roman_config["FILTER_LIST"]
            .replace("roman/roman_", "")
            .replace(".pb", "")
            .split(",")
        )
        # in the asdf template file we only have the flux in
        # the F158 filter so we're adding the other filters
        roman_filter_params = [
            x.replace("F158", "")
            for x in self.roman_catalog_template.source_catalog.columns
            if "F158" in x
        ]

        # # first, clear the template
        # self.roman_catalog_template.source_catalog.remove_rows(slice(None))
        self.roman_catalog_template.source_catalog.add_column(catalog["id"], name="id")

        # then add the simulated data
        for filter_name in filter_list:
            for param in roman_filter_params:
                new_column = f"{filter_name}{param}"
                if new_column not in self.roman_catalog_template.source_catalog.columns:
                    # add new column
                    if "flux" in new_column:
                        # add flux and error columns for each filter
                        simulated_colname = (
                            f"magnitude_{filter_name}_err"
                            if "err" in new_column
                            else f"magnitude_{filter_name}"
                        )
                        self.roman_catalog_template.source_catalog.add_column(
                            catalog[simulated_colname], name=new_column
                        )
                    else:
                        # copy parameter from F158
                        simulated_colname = new_column
                        self.roman_catalog_template.source_catalog.add_column(
                            self.roman_catalog_template.source_catalog[f"F158{param}"],
                            name=new_column,
                        )

                else:
                    # replace column data
                    if "flux" in new_column:
                        simulated_colname = (
                            f"magnitude_{filter_name}_err"
                            if "err" in new_column
                            else f"magnitude_{filter_name}"
                        )
                        self.roman_catalog_template.source_catalog[new_column] = (
                            catalog[simulated_colname]
                        )

        self.roman_catalog_template.source_catalog.add_column(
            catalog["context"], name="context"
        )
        self.roman_catalog_template.source_catalog.add_column(
            catalog["zspec"], name="zspec"
        )
        self.roman_catalog_template.source_catalog.add_column(
            catalog["z_true"], name="string_data"
        )

    def save_catalog(
        self,
        output_path: str = LEPHAREWORK,
        output_filename: str = DEFAULT_OUTPUT_CATALOG_FILENAME,
    ):
        """
        Save the simulated input catalog to a file.

        Parameters
        ----------
        output_filename : str, optional
            The filename to save the catalog to.
        """
        output_path = Path(output_path).as_posix()
        output_filename = output_filename
        logger.info(f"Saving catalog to {output_path}/{output_filename}...")
        self.roman_catalog_template.save(output_filename, dir_path=output_path)
        logger.info("Catalog saved successfully")

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
        catalog = rfn.append_fields(catalog, "id", ids, usemask=False)

        new_dtype = [("id", catalog["id"].dtype)] + [
            (name, catalog[name].dtype) for name in catalog.dtype.names if name != "id"
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
        filter_list = (
            self.lephare_config.get("FILTER_LIST")
            .replace(".pb", "")
            .replace("roman/roman_", "")
            .split(",")
        )
        with open(catalog_name) as f:
            # BEWARE of the format of LAPHEREWORK/lib_mag/*_COSMOS.dat!
            # ignore the first N_filt lines in the file
            for _ in range(len(filter_list) + 1):
                next(f)
            colname_list = f.readline().strip().split(" ")
        colnames = [x for x in colname_list if "[N_filt]" not in x]
        colvector = [x for x in colname_list if "[N_filt]" in x]
        expanded_colvector = [
            x.replace("vector", filter_name)
            for x in colvector
            for filter_name in filter_list
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

    def process(
        self,
        output_path: str = "",
        output_filename: str = DEFAULT_OUTPUT_CATALOG_FILENAME,
        nobj=100,
    ):
        """
        Run the process to create the simulated catalog.
        """
        self.get_filters()
        self.create_simulated_data()
        self.create_simulated_input_catalog(
            output_filename=output_filename, output_path=output_path, nobj=nobj,
        )

        logger.info("DONE")


if __name__ == "__main__":

    def parse_args():
        parser = argparse.ArgumentParser(
            description="Create a simulated catalog using the Roman telescope data."
        )
        parser.add_argument(
            "--output_path",
            type=str,
            default=LEPHAREWORK,
            help="Path to save the output catalog.",
        )
        parser.add_argument(
            "--output_filename",
            type=str,
            default=DEFAULT_OUTPUT_CATALOG_FILENAME,
            help="Filename for the output catalog.",
        )
        parser.add_argument(
            '--nobj', type=int, default=100,
            help='Number of objects to simulate.')
        return parser.parse_args()

    args = parse_args()

    logger.info("Starting simulated catalog creation...")
    rcp = SimulatedCatalog()
    rcp.process(args.output_path, args.output_filename, nobj=args.nobj)
    logger.info("Simulated catalog creation completed successfully")
