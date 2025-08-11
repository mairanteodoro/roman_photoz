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
import astropy.table
from astropy.table import Table
from rail.core.stage import RailStage
from rail.estimation.algos.lephare import LephareEstimator, LephareInformer

from roman_photoz.default_config_file import default_roman_config
from roman_photoz.logger import logger
from roman_photoz.roman_catalog_handler import RomanCatalogHandler
from roman_photoz.utils import read_output_keys
import argparse
import sys

DS = RailStage.data_store
DS.__class__.allow_overwrite = True

LEPHAREDIR = Path(os.environ.get("LEPHAREDIR", lp.LEPHAREDIR))
LEPHAREWORK = os.environ.get("LEPHAREWORK", (LEPHAREDIR / "work").as_posix())

# default paths and filenames
DEFAULT_OUTPUT_KEYWORDS = Path(
    pkg_resources.resource_filename(__name__, "data/default_roman_output.para")
).as_posix()


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
        # set attributes used for determining the redshift
        self.flux_cols: list = []
        self.flux_err_cols: list = []
        self.inform_stage = None
        self.estimated = None
        self.default_roman_output_keys = read_output_keys(DEFAULT_OUTPUT_KEYWORDS)

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
        input_filename,
        fit_colname: str = "segment_{}_flux",
        fit_err_colname: str = "segment_{}_flux_err",
    ) -> Table:
        """
        Fetch the data from the input file.

        Parameters
        ----------
        input_filename : str, optional
            Name of the input file.

        Returns
        -------
        Table
            The catalog data.
        """
        # full qualified path to the catalog file
        logger.info(f"Reading catalog from {input_filename}")

        # read in catalog data
        handler = RomanCatalogHandler(
            input_filename, fit_colname=fit_colname, fit_err_colname=fit_err_colname
        )

        # Populate flux_cols and flux_err_cols from the handler's filter names
        self.flux_cols = [
            fit_colname.format(filter_id) for filter_id in handler.filter_names
        ]
        self.flux_err_cols = [
            fit_err_colname.format(filter_id) for filter_id in handler.filter_names
        ]

        # Convert numpy structured array to astropy Table for RAIL compatibility
        return Table(handler.catalog)

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

        # following LePhare default recommendations, some
        # different settings for stars / galaxies / quasars
        star_overrides = {}
        gal_overrides = {
            "MOD_EXTINC": "18,26,26,33,26,33,26,33",
            "EXTINC_LAW": "SMC_prevot.dat,SB_calzetti.dat,SB_calzetti_bump1.dat,SB_calzetti_bump2.dat",
            "EM_LINES": "EMP_UV",
            "EM_DISPERSION": "0.5,1.,1.5",
        }
        qso_overrides = {
            "MOD_EXTINC": "0,1000",
            "EB_V": "0.,0.1,0.2,0.3",
            "EXTINC_LAW": "SB_calzetti.dat",
        }

        self.inform_stage = LephareInformer.make_stage(
            name="inform_roman",
            nondetect_val=np.nan,
            model=self.informer_model_path,
            hdf5_groupname="",
            lephare_config=self.config,
            bands=self.flux_cols,
            err_bands=self.flux_err_cols,
            ref_band=self.flux_cols[0],
            zmin=zmin,
            zmax=zmax,
            nzbins=nzbins,
            star_config=star_overrides,
            gal_config=gal_overrides,
            qso_config=qso_overrides,
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
        )

        # dh = estimate_lephare.add_data('input', self.data)
        self.estimated = estimate_lephare.estimate(self.data)

    def save_results(
        self,
        output_filename: str = None,
        output_format: str = "parquet",
    ):
        """
        Save the results to the specified output file.

        Parameters
        ----------
        output_filename : str, optional
            Name of the output file.
        output_format : str, optional
            Format to save the results.
            Supported formats are "parquet" (default) and "asdf".

        Raises
        ------
        ValueError
            If there are no results to save.
        """
        if self.estimated is not None:
            ancil_data = self.estimated.data.ancil
        else:
            logger.error("No results to save")
            raise ValueError("No results to save.")

        if output_format.lower() == "parquet":
            ancil_data = Table(ancil_data)
            ancil_data.write(output_filename, format="parquet", overwrite=True)
        elif output_format.lower() == "asdf":
            tree = {"roman_photoz_results": ancil_data}
            with AsdfFile(tree) as af:
                af.write_to(output_filename)
        logger.info(f"Results saved to {output_filename}.")

    def update_input(self, input_filename):
        import pyarrow as pa
        import pyarrow.parquet as pq
        tab = pq.read_table(input_filename)
        tab_astro = Table.read(input_filename)
        meta = dict(tab.schema.metadata)

        namedict = {
            'photoz': 'Z_BEST',
            'photoz_high68': 'Z_BEST68_HIGH',
            'photoz_high90': 'Z_BEST90_HIGH',
            'photoz_high99': 'Z_BEST99_HIGH',
            'photoz_low68': 'Z_BEST68_LOW',
            'photoz_low90': 'Z_BEST90_LOW',
            'photoz_low99': 'Z_BEST99_LOW',
            'photoz_gof': 'CHI_BEST',
            'photoz_sed': 'MOD_BEST',
        }
        for newname, oldname in namedict.items():
            tab_astro[newname] = self.estimated.data.ancil[oldname]
            tab = tab.append_column(
                newname, pa.array(self.estimated.data.ancil[oldname]))
            # annoying to duplicate this, but we add to the "real"
            # parquet table and also the astropy version to get the
            # right astropy metadata

        extra_astropy_metadata = astropy.table.meta.get_yaml_from_table(
            tab_astro)
        meta[b"table_meta_yaml"] = "\n".join(
            extra_astropy_metadata).encode('utf-8')
        tab = tab.replace_schema_metadata(meta)
        pq.write_table(tab, input_filename)


    def process(
        self,
        input_filename,
        output_filename: str = None,
        output_format: str = "parquet",
        fit_colname: str = "segment_{}_flux",
        fit_err_colname: str = "segment_{}_flux_err",
    ):
        """
        Process the Roman catalog data.

        Parameters
        ----------
        input_filename : str
            Name of the input file.
        output_filename : str, optional
            Name of the output file.
        output_format : str, optional
            Format to save the results.
            Supported formats are "parquet" (default) and "asdf."
        flux_type : str, optional
            The type of flux to use for fitting.
            Options are "psf" (default), "kron", "segment", or "aperture."
        """
        self.data = self.get_data(
            input_filename=input_filename,
            fit_colname=fit_colname,
            fit_err_colname=fit_err_colname,
        )

        if not self.informer_model_exists:
            print(
                "Warning: The informer model file does not exist. Creating a new one..."
            )
            self.create_informer_stage()
        self.create_estimator_stage()

        if output_filename is not None:
            self.save_results(
                output_filename=output_filename,
                output_format=output_format,
            )
        else:
            self.update_input(input_filename)


    @property
    def informer_model_exists(self):
        """
        Check if the informer model file exists.

        Returns
        -------
        bool
            True if the model file exists, False otherwise.
        """
        if os.path.exists(self.informer_model_path):
            print(
                f"The informer model file {self.informer_model_path} exists. Using it..."
            )
            return True
        return False

    @property
    def informer_model_path(self):
        """
        Get the path to the informer model file.

        The path is determined by checking the INFORMER_MODEL_PATH environment variable first,
        falling back to LEPHAREWORK if not set.

        Returns
        -------
        str
            The path to the informer model file.
        """
        informer_path = os.environ.get(
            "INFORMER_MODEL_PATH", os.environ.get("LEPHAREWORK", "")
        )
        return Path(informer_path, self.model_filename).as_posix()


def _get_parser():
    """
    Main function to process Roman catalog data using command-line arguments.
    This function parses command-line arguments for input/output files, configuration,
    model files, and processing options, then runs the RomanCatalogProcess accordingly.
    """

    parser = argparse.ArgumentParser(description="Process Roman catalog data.")
    parser.add_argument(
        "--config-filename",
        type=str,
        default="",
        help="Path to the configuration file (default: use default Roman config).",
        required=False,
    )
    parser.add_argument(
        "--model-filename",
        type=str,
        default="roman_model.pkl",
        help="Name of the pickle model file (default: roman_model.pkl).",
        required=False,
    )
    parser.add_argument(
        "--input-filename",
        type=str,
        help=f"Input catalog filename",
    )
    parser.add_argument(
        "--output-format",
        type=str,
        default="parquet",
        help='Format in which to save the results. Supported formats are "parquet" (default) and "asdf".',
    )
    parser.add_argument(
        "--output-filename",
        type=str,
        default=None,
        help=f"Output filename (default: None).  If None, update input filename in place.",
    )
    parser.add_argument(
        "--fit-colname",
        type=str,
        default="segment_{}_flux",
        help="Template for the column name to be used for fitting fluxes/mags. It should contain a pair of curly braces as a placeholder for the filter ID, e.g., 'segment_{}_flux'.",
    )
    parser.add_argument(
        "--fit-err-colname",
        type=str,
        default="segment_{}_flux_err",
        help="Template for the column name containing the error corresponding to fit_colname. It should contain a pair of curly braces as a placeholder for the filter ID, e.g., 'segment_{}_flux_err'.",
    )
    return parser


def main():
    """
    Main function to process Roman catalog data.
    """

    parser = _get_parser()
    args = parser.parse_args()

    logger.info("Starting Roman catalog processing")
    rcp = RomanCatalogProcess(
        config_filename=args.config_filename, model_filename=args.model_filename
    )
    rcp.process(
        input_filename=args.input_filename,
        output_filename=args.output_filename,
        output_format=args.output_format,
        fit_colname=args.fit_colname,
        fit_err_colname=args.fit_err_colname,
    )
    logger.info("Roman catalog processing completed")
