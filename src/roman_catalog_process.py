### COSMOS example with rail+lephare ###

from rail.estimation.algos.lephare import LephareInformer, LephareEstimator
import numpy as np
import lephare as lp
from rail.core.stage import RailStage
import matplotlib.pyplot as plt
from astropy.table import Table
from collections import OrderedDict
import os


DS = RailStage.data_store
DS.__class__.allow_overwrite = True


class RomanCatalogProcess:
    def __init__(self):
        self.data = OrderedDict()
        # set configuration file (roman will have its own)
        self.lephare_config = lp.default_cosmos_config
        # set redshift grid (step, z_i, z_f)
        self.lephare_config["Z_STEP"] = ".1,0.,7."
        # max number of objects to process from input catalog
        self.nobj = 100
        # set attributes used for determining the redshift
        self.flux_cols = []
        self.flux_err_cols = []
        self.inform_stage = None
        self.estimated = None

    def get_data(self):
        # N.B.: This is the method that will fetch multiband
        # roman catalog when it is available by using
        # the roman_catalog_handler.py module.
        # For now, just for the sake of implementation, we'll
        # be using data from the COSMOS example.

        lp.data_retrieval.get_auxiliary_data(
            keymap=self.lephare_config,
            additional_files=["examples/COSMOS.in", "examples/output.para"],
        )

        bands = self.lephare_config["FILTER_LIST"].split(",")
        print(len(bands))

        # set limit to the first 100 objects
        cosmos = Table.read(
            os.path.join(lp.LEPHAREDIR, "examples/COSMOS.in"), format="ascii"
        )[: self.nobj]

        # loop over the filters we want to keep to get
        # the number of the filter, n, and the name, b
        for n, b in enumerate(bands):
            flux = cosmos[cosmos.colnames[1 + 2 * n]]
            flux_err = cosmos[cosmos.colnames[2 + 2 * n]]
            self.data[f"flux_{b}"] = flux
            self.flux_cols.append(f"flux_{b}")
            self.data[f"flux_err_{b}"] = flux_err
            self.flux_err_cols.append(f"flux_err_{b}")
        self.data["redshift"] = np.array(cosmos[cosmos.colnames[-2]])

    def create_informer_stage(self):
        # use the inform stage to create the library of SEDs with
        # various redshifts, extinction parameters, and reddening values.
        self.inform_stage = LephareInformer.make_stage(
            name="inform_COSMOS",
            nondetect_val=np.nan,
            model="lephare.pkl",
            hdf5_groupname="",
            lephare_config=self.lephare_config,
            bands=self.flux_cols,
            err_bands=self.flux_err_cols,
            ref_band=self.flux_cols[0],
        )
        self.inform_stage.inform(self.data)

    def create_estimator_stage(self):
        # take the sythetic test data, and find the best
        # fits from the library. This results in a PDF, zmode,
        # and zmean for each input test data.
        estimate_lephare = LephareEstimator.make_stage(
            name="test_Lephare_COSMOS",
            nondetect_val=np.nan,
            model=self.inform_stage.get_handle("model"),
            hdf5_groupname="",
            aliases=dict(input="test_data", output="lephare_estim"),
            bands=self.flux_cols,
            err_bands=self.flux_err_cols,
            ref_band=self.flux_cols[0],
        )

        self.estimated = estimate_lephare.estimate(self.data)

    def process(self):
        self.get_data()
        self.create_informer_stage()
        self.create_estimator_stage()


if __name__ == "__main__":

    rcp = RomanCatalogProcess()
    rcp.process()

    print("Done.")
