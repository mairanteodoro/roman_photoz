"""Example test demonstrating usage of the bigdata test framework."""

from importlib.resources import files
from pathlib import Path

import numpy as np
import pytest
from astropy.stats import mad_std
from astropy.table import Table

from roman_photoz import create_simulated_catalog
from roman_photoz.default_config_file import default_roman_config
from roman_photoz.roman_catalog_process import RomanCatalogProcess

# file containing the default output keys that the output file should have
# Modern approach using importlib.resources
DEFAULT_OUTPUT_KEYWORDS = str(
    files("roman_photoz").joinpath("data/default_roman_output.para")
)


@pytest.fixture
def roman_catalog_process():
    """Create a basic RomanCatalogProcess instance for testing"""
    return RomanCatalogProcess(config_filename=default_roman_config)


def test_roman_photoz(tmp_path, dms_logger):
    # create catalog
    sc = create_simulated_catalog.SimulatedCatalog(nobj=100, mag_noise=0.01, seed=42)
    sc.process(tmp_path, "cat.parquet")

    # create instance
    rcp = RomanCatalogProcess(
        config_filename=default_roman_config,
    )

    input_filename = Path(tmp_path) / "cat.parquet"
    rcp.process(input_filename=input_filename)

    output = Table.read(input_filename, format="parquet")

    # get the expected column names
    expected_cols = [
        "photoz",
        "photoz_high99",
        "photoz_high90",
        "photoz_high68",
        "photoz_low99",
        "photoz_low90",
        "photoz_low68",
        "photoz_gof",
        "photoz_sed",
    ]

    # For now, we will just check that all the expected columns are present
    # and at least vaguely populated
    for col in expected_cols:
        assert col in output.columns
        assert np.any(output[col] != 0)

    # make sure the redshifts aren't crazy.
    err_upper_limit = 0.2
    err = mad_std(output["photoz"] - output["redshift_true"])
    dms_logger.info(
        f"""DMS398 MSG: roman-photoz successfully produced output file
        containing photometric redshifts with a MAD std <= {err_upper_limit:.3f}?
        {err < err_upper_limit} (actual value: {err:.3f})"""
    )
    assert err < err_upper_limit
