### COSMOS example with rail+lephare ###
import argparse
import json
import os
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Union

import lephare as lp
import numpy as np
import pkg_resources
from asdf import AsdfFile
from astropy.table import Table
from rail.core.stage import RailStage
from rail.estimation.algos.lephare import LephareEstimator, LephareInformer

from roman_photoz.default_config_file import default_roman_config
from roman_photoz.logger import logger
from roman_photoz.roman_catalog_handler import RomanCatalogHandler

DS = RailStage.data_store
DS.__class__.allow_overwrite = True

LEPHAREDIR = os.environ.get("LEPHAREDIR", lp.LEPHAREDIR)
LEPHAREWORK = os.environ.get(
    "LEPHAREWORK", (Path(LEPHAREDIR).parent / "work").as_posix()
)
# default paths and filenames
DEFAULT_INPUT_FILENAME = "roman_simulated_catalog.asdf"
DEFAULT_INPUT_PATH = LEPHAREWORK
DEFAULT_OUTPUT_FILENAME = "roman_photoz_results.asdf"
DEFAULT_OUTPUT_PATH = LEPHAREWORK

CWD = os.getcwd()


class RomanCatalogProcess:
    """
    A class to process Roman catalog data using rail and lephare.

    Attributes
    ----------
    data : dict
        Dictionary to store the processed data.
    flux_cols : list
        List of flux columns.
    flux_err_cols : list
        List of flux error columns.
    inform_stage : RailStage
        Informer stage for creating the library of SEDs.
    estimated : RailStage
        Estimator stage for finding the best fits from the library.
    model_filename : str
        Name of the pickle model file.
    """

    def __init__(
        self,
        config_filename: Union[dict, str] = "",
        model_filename: str = "roman_model.pkl",
    ):
        """
        Initialize the RomanCatalogProcess instance.

        Parameters
        ----------
        config_filename : Union[dict, str], optional
            Path to the configuration file or a configuration dictionary.
        model_filename : str, optional
            Name of the pickle model file (default: "roman_model.pkl").
        """
        self.data: dict = OrderedDict()
        # set configuration file (roman will have its own)
        self.set_config_file(config_filename)
        # set model filename
        self.model_filename = model_filename
        self.informer_model_path = Path(LEPHAREWORK, self.model_filename).as_posix()
        # set attributes used for determining the redshift
        self.flux_cols: list = []
        self.flux_err_cols: list = []
        self.inform_stage = None
        self.estimated = None
        # read in the elements from default_roman_output.para
        default_output_file = Path(
            pkg_resources.resource_filename(__name__, "data/default_roman_output.para")
        )
        if default_output_file.exists():
            with open(default_output_file) as f:
                self.default_roman_output_keys = [
                    line.strip()
                    for line in f
                    if line.strip() and not line.startswith("#")
                ]

    def set_config_file(self, config_filename: Union[dict, str] = ""):
        """
        Set the configuration file.

        Parameters
        ----------
        config_filename : Union[dict, str], optional
            Path to the configuration file in JSON format or a configuration dictionary.
        """
        if isinstance(config_filename, str):
            if config_filename:
                # a config filename was provided in JSON format
                with open(config_filename) as f:
                    self.config = json.load(f)
            else:
                # use default Roman config file
                self.config = default_roman_config
        else:
            # a config was provided in dict format
            self.config = config_filename

    def get_data(
        self,
        input_filename: str = DEFAULT_INPUT_FILENAME,
        input_path: str = DEFAULT_INPUT_PATH,
    ) -> Table:
        """
        Fetch the data from the input file.

        Parameters
        ----------
        input_filename : str, optional
            Name of the input file.
        input_path : str, optional
            Path to the input file.

        Returns
        -------
        Table
            The catalog data.
        """
        # full qualified path to the catalog file
        filename = Path(input_path, input_filename).as_posix()
        logger.info(f"Reading catalog from {filename}")

        # read in catalog data
        if Path(filename).suffix == ".asdf":
            # Roman catalog
            handler = RomanCatalogHandler(filename)
            cat_data = Table(handler.process())
        else:
            # custom catalog
            cat_data = Table.read(filename, format="ascii.no_header")

        return cat_data

    def format_data(self, cat_data: Table):
        """
        Format the catalog data.

        Parameters
        ----------
        cat_data : Table
            The catalog data.
        """
        # get information about Roman filters
        bands = self.config["FILTER_LIST"].split(",")
        logger.debug(f"Found {len(bands)} bands in filter list")

        # loop over the filters we want to keep to get
        # the number of the filter, n, and the name, b
        # (the final data has to have  2 * n_bands + 4 columns)
        for n, b in enumerate(bands):
            flux = cat_data[cat_data.colnames[1 + 2 * n]].astype(float)
            flux_err = cat_data[cat_data.colnames[2 + 2 * n]].astype(float)
            self.data[f"flux_{b.split('_')[1].split('.')[0]}"] = flux
            self.flux_cols.append(f"flux_{b.split('_')[1].split('.')[0]}")
            self.data[f"flux_err_{b.split('_')[1].split('.')[0]}"] = flux_err
            self.flux_err_cols.append(f"flux_err_{b.split('_')[1].split('.')[0]}")
        self.data["context"] = np.array(cat_data[cat_data.colnames[-3]]).astype(int)
        self.data["redshift"] = np.array(cat_data[cat_data.colnames[-2]]).astype(float)
        self.data["string_data"] = np.array(cat_data[cat_data.colnames[-1]]).astype(
            bytes
        )
        logger.info("Catalog data formatted successfully")

    def create_informer_stage(self):
        """
        Create the informer stage to generate the library of SEDs with various parameters.
        """
        # use the inform stage to create the library of SEDs with
        # various redshifts, extinction parameters, and reddening values.
        # -> Informer will produce as output a generic "model",
        #    the details of which depends on the sub-class.
        # |we use rail's interface here to create the informer stage
        # |https://rail-hub.readthedocs.io/en/latest/api/rail.estimation.informer.html

        # set up the informer stage with info from the config file (Z_STEP, ZMIN, ZMAX)
        z_grid = self.config["Z_STEP"].split(",")
        zstep = float(z_grid[0])
        zmin = float(z_grid[1])
        zmax = float(z_grid[2])
        # we need to pass nzbins to the informer stage instead
        # of zstep, which will be calculated by the informer at runtime
        nzbins = (zmax - zmin) / zstep

        self.inform_stage = LephareInformer.make_stage(
            name="inform_roman",
            nondetect_val=np.nan,
            model=self.informer_model_path,
            hdf5_groupname="",
            lephare_config=self.config,
            # star_config=None,
            # qso_config=None,
            bands=self.flux_cols,
            err_bands=self.flux_err_cols,
            ref_band=self.flux_cols[0],
            zmin=zmin,
            zmax=zmax,
            nzbins=nzbins,
        )
        self.inform_stage.inform(self.data)

    def create_estimator_stage(self):
        """
        Create the estimator stage to find the best fits from the library.
        """
        # take the sythetic test data, and find the best
        # fits from the library. This results in a PDF, zmode,
        # and zmean for each input test data.
        # -> Estimators use a generic "model", apply the photo-z estimation
        #    and provide as "output" a QPEnsemble, with per-object p(z).
        # |we use rail's interface here to create the estimator stage
        # |https://rail-hub.readthedocs.io/en/latest/api/rail.estimation.estimator.html
        if self.informer_model_exists:
            model = self.informer_model_path
        else:
            model = self.inform_stage.get_handle("model")
        estimate_lephare = LephareEstimator.make_stage(
            name="estimate_roman",
            nondetect_val=np.nan,
            model=model,
            hdf5_groupname="",
            aliases=dict(input="test_data", output="lephare_estim"),
            bands=self.flux_cols,
            err_bands=self.flux_err_cols,
            ref_band=self.flux_cols[0],
            output_keys=self.default_roman_output_keys,
            lephare_config=self.config,
            # star_config=None,
            # qso_config=None,
        )

        self.estimated = estimate_lephare.estimate(self.data)

    def save_results(
        self,
        output_filename: str = DEFAULT_OUTPUT_FILENAME,
        output_path: str = LEPHAREWORK,
    ):
        """
        Save the results to the specified output file.

        Parameters
        ----------
        output_filename : str, optional
            Name of the output file.
        output_path : str, optional
            Path to the output file.

        Raises
        ------
        ValueError
            If there are no results to save.
        """
        output_filename = Path(output_path, output_filename).as_posix()
        if self.estimated is not None:
            ancil_data = self.estimated.data.ancil
        else:
            logger.error("No results to save")
            raise ValueError("No results to save.")

        tree = {"roman_photoz_results": ancil_data}
        with AsdfFile(tree) as af:
            af.write_to(output_filename)

        logger.info(f"Results saved to {output_filename}")

    def process(
        self,
        input_filename: str = DEFAULT_INPUT_FILENAME,
        input_path: str = DEFAULT_INPUT_PATH,
        output_filename: str = DEFAULT_OUTPUT_FILENAME,
        output_path: str = DEFAULT_OUTPUT_PATH,
        save_results: bool = True,
    ):
        """
        Process the Roman catalog data.

        Parameters
        ----------
        input_filename : str, optional
            Name of the input file.
        input_path : str, optional
            Path to the input file.
        output_filename : str, optional
            Name of the output file.
        output_path : str, optional
            Path to the output file.
        save_results : bool, optional
            Whether to save the results.
        """
        cat_data = self.get_data(input_filename=input_filename, input_path=input_path)

        self.format_data(cat_data)
        if not self.informer_model_exists:
            print(
                "Warning: The informer model file does not exist. Creating a new one..."
            )
            self.create_informer_stage()
        self.create_estimator_stage()

        if save_results:
            self.save_results(output_filename=output_filename, output_path=output_path)


def main():

    parser = argparse.ArgumentParser(description="Process Roman catalog data.")
    parser.add_argument(
        "--config_filename",
        type=str,
        default="",
        help="Path to the configuration file (default: use default Roman config).",
        required=False,
    )
    parser.add_argument(
        "--model_filename",
        type=str,
        default="roman_model.pkl",
        help="Name of the pickle model file (default: roman_model.pkl).",
        required=False,
    )
    parser.add_argument(
        "--input_path",
        type=str,
        default=DEFAULT_INPUT_PATH,
        help=f"Path to the catalog file (default: {DEFAULT_INPUT_PATH}).",
    )
    parser.add_argument(
        "--input_filename",
        type=str,
        default=DEFAULT_INPUT_FILENAME,
        help=f"Input catalog filename (default: {DEFAULT_INPUT_FILENAME}).",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default=DEFAULT_OUTPUT_PATH,
        help=f"Path to where the results will be saved (default: {DEFAULT_OUTPUT_PATH}).",
    )
    parser.add_argument(
        "--output_filename",
        type=str,
        default=DEFAULT_OUTPUT_FILENAME,
        help=f"Output filename (default: {DEFAULT_OUTPUT_FILENAME}).",
    )
    parser.add_argument(
        "--save_results",
        type=bool,
        default=True,
        help="Save results? (default: True).",
    )
    return parser


def main():
    """
    Main function to process Roman catalog data.
    """

    parser = _get_parser()
    args = parser.parse_args()

    try:
        logger.info("Starting Roman catalog processing")
        rcp = RomanCatalogProcess(
            config_filename=args.config_filename, model_filename=args.model_filename
        )
        rcp.process(
            input_filename=args.input_filename,
            input_path=args.input_path,
            output_filename=args.output_filename,
            output_path=args.output_path,
            save_results=args.save_results,
        )
        logger.info("Roman catalog processing completed")
    except Exception as e:
        logger.error(f"An error occurred during processing: {str(e)}")
        sys.exit(1)
