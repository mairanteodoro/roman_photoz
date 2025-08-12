import os
from pathlib import Path

import numpy as np
from astropy.table import Table
from numpy.lib import recfunctions as rfn
from roman_datamodels import datamodels as rdm

from roman_photoz.logger import logger
from roman_photoz.utils import get_roman_filter_list
import astropy.units as u
import math


class RomanCatalogHandler:
    """
    A class to handle Roman catalog operations including reading and formatting it in a suitable way for roman_photoz.
    """

    def __init__(
        self,
        catname: str = "",
        fit_colname: str = "segment_{}_flux",
        fit_err_colname: str = "segment_{}_flux_err",
    ):
        """
        Initialize the RomanCatalogHandler with a catalog name and the name of the columns to be used for fitting.

        Parameters
        ----------
        catname : str, optional
            The name of the catalog file (default is an empty string).
        fit_colname : str
            Name of the column to be used for fitting.
            It should contain a pair of curly braces as a placeholder for the filter ID, e.g., "segment_{}_flux".
        fit_err_colname : str
            Name of the column containing the error corresponding to fit_colname.
            It should contain a pair of curly braces as a placeholder for the filter ID, e.g., "segment_{}_flux_err".
        """
        self.cat_name = catname
        self.fit_colname = fit_colname
        self.fit_err_colname = fit_err_colname
        self.cat_temp_filename = "cat_temp_file.csv"
        self.filter_names = get_roman_filter_list()
        self.cat_array = None
        self.catalog = None

        # Only read and format catalog if a filename is provided
        if catname:
            self.process()

    def format_catalog(self):
        """
        Format the catalog by appending necessary fields and columns.
        """
        logger.info("Formatting catalog...")
        # Initialize catalog if it's empty or None
        if self.catalog is None or len(self.catalog) == 0:
            self.catalog = Table()

        # Only add label if it's not already present
        if "label" not in self.catalog.dtype.names:
            self.catalog['label'] = self.cat_array['label']

        for filter_id in self.filter_names:
            # Roman filter ID in format "fNNN"
            fit_colname = self.fit_colname.format(filter_id)
            fit_err_colname = self.fit_err_colname.format(filter_id)

            if fit_colname in self.cat_array.dtype.names:
                value = np.array(self.cat_array[fit_colname])
                error = np.array(self.cat_array[fit_err_colname])
            else:
                # https://lephare.readthedocs.io/en/latest/detailed.html#context
                # https://lephare.readthedocs.io/en/latest/detailed.html#the-information-needed-for-the-fit
                # "If the context is absent in the input catalog (format SHORT), or put at 0, it is
                # equivalent to use all the passbands for all the objects.
                # However, the code checks the error and flux values.
                # If both values are negative, the band is not used."
                value = np.full(len(self.cat_array), -99, dtype=np.float32)
                error = np.full(len(self.cat_array), -99, dtype=np.float32)

            # Only add fields if they don't already exist
            if fit_colname not in self.catalog.dtype.names:
                self.catalog[fit_colname] = value

            if fit_err_colname not in self.catalog.dtype.names:
                self.catalog[fit_err_colname] = error

            # lephare expects fluxes in erg/s/cm^2/Hz
            # we need to convert from nJy
            # 10^-23 erg / s / ... = 1 Jy
            # 10^-9 Jy = 1 nJy
            # => 10^-32 erg / s / ... = 1 nJy
            m = self.catalog[fit_err_colname] > 0
            self.catalog[fit_colname][m] *= 10**-32
            self.catalog[fit_err_colname][m] *= 10**-32

        if "redshift" not in self.cat_array.dtype.names:
            self.catalog['redshift'] = np.zeros(len(self.catalog), dtype='f4')
        else:
            self.catalog['redshift'] = self.cat_array['redshift']

        logger.info("Catalog formatting completed")

    def read_catalog(self):
        """
        Read the catalog file and convert it to a numpy structured array.
        """
        logger.info(f"Reading catalog {self.cat_name}...")

        if Path(self.cat_name).suffix == ".asdf":
            dm = rdm.open(self.cat_name)
            # Convert Table to numpy structured array
            cat_array = dm.source_catalog.as_array()
        elif Path(self.cat_name).suffix == ".parquet":
            cat_array = Table.read(self.cat_name)
        else:
            raise ValueError(f"Unsupported catalog file type: {self.cat_name}")

        logger.info("Catalog read successfully")
        return cat_array

    def process(self):
        """
        Process the catalog by reading and formatting it.

        Returns
        -------
        np.ndarray
            The formatted catalog.
        """
        if self.cat_array is None:
            self.cat_array = self.read_catalog()
        if self.catalog is None or len(self.catalog) == 0:
            self.catalog = np.empty(0, dtype=[])
            self.format_catalog()
        return self.catalog


if __name__ == "__main__":
    data_path = Path(__file__).parent / "data"
    test_cat = (
        data_path / "r00001_p_v01001001001001_270p65x49y70_f158_mbcat_cat.parquet"
    ).as_posix()

    catalog_handler = RomanCatalogHandler(
        catname=test_cat,
        fit_colname="segment_{}_flux",
        fit_err_colname="segment_{}_flux_err",
    )
