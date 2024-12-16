from pathlib import Path
import os
from roman_datamodels import datamodels as rdm


class RomanCatalogHandler:
    def __init__(self, catname: str = ""):
        self.cat_name = catname
        self.cat_df = None
        self.catalog = None
        self.cat_temp_filename = "cat_temp_file.h5"

    def format_catalog(self):
        print("Formatting catalog...")
        self.catalog = self.cat_df[["flux_psf", "flux_psf_err"]]

    def save_catalog(self):
        print(f"Saving catalog {self.cat_temp_filename}...")
        if self.catalog is not None:
            self.catalog.to_hdf(self.cat_temp_filename, key="catalog")
        else:
            print("No catalog to save.")

    def read_catalog(self):
        print(f"Parsing catalog {self.cat_name}...")
        dm = rdm.open(self.cat_name)
        self.cat_df = dm.source_catalog.to_pandas()
        print("Done.")

    def add_to_phot_par(self):
        pass

    def process(self):
        self.read_catalog()
        self.format_catalog()
        self.save_catalog()
        self.add_to_phot_par()


if __name__ == "__main__":

    test_bigdata = os.getenv("TEST_BIGDATA")
    if test_bigdata is None:
        raise ValueError("Environment variable TEST_BIGDATA is not set")
    reg_test_data = Path(test_bigdata)

    test_cat = reg_test_data / "r0000101001001001001_0001_wfi01_cat.asdf"

    catalog_handler = RomanCatalogHandler(test_cat.as_posix())

    catalog_handler.process()

    print("Done.")
