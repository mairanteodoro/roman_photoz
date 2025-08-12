"""Example test demonstrating usage of the bigdata test framework."""

from pathlib import Path

import pytest
from astropy.table import Table
import numpy as np

try:
    from importlib.resources import files
except ImportError:
    # Fallback for Python < 3.9
    from importlib_resources import files

from roman_photoz.default_config_file import default_roman_config
from roman_photoz.roman_catalog_process import RomanCatalogProcess
from roman_photoz import create_simulated_catalog

from astropy.stats import mad_std

# file containing the default output keys that the output file should have
try:
    # Modern approach using importlib.resources
    DEFAULT_OUTPUT_KEYWORDS = str(
        files("roman_photoz").joinpath("data/default_roman_output.para")
    )
except (ImportError, AttributeError):
    # Fallback for older Python versions or if importlib_resources not available
    import pkg_resources

    DEFAULT_OUTPUT_KEYWORDS = pkg_resources.resource_filename(
        "roman_photoz", "data/default_roman_output.para"
    )


@pytest.fixture
def roman_catalog_process():
    """Create a basic RomanCatalogProcess instance for testing"""
    return RomanCatalogProcess(config_filename=default_roman_config)


@pytest.mark.bigdata
def test_roman_photoz(tmp_path):
    # create catalog
    sc = create_simulated_catalog.SimulatedCatalog(nobj=10000, mag_noise=0.02)
    sc.process(tmp_path, 'cat.parquet')

    # create instance
    rcp = RomanCatalogProcess(
        config_filename=default_roman_config,
    )

    input_filename = Path(tmp_path) / 'cat.parquet'
    rcp.process(input_filename=input_filename)

    output = Table.read(input_filename, format="parquet")

    # get the expected column names
    expected_cols = ['photoz',
                      'photoz_high99', 'photoz_high90', 'photoz_high68',
                      'photoz_low99', 'photoz_low90', 'photoz_low68',
                      'photoz_gof', 'photoz_sed']

    # For now, we will just check that all the expected columns are present
    # and at least vaguely populated
    for col in expected_cols:
        assert col in output.columns
        assert np.any(output[col] != 0)
    # make sure the redshifts aren't crazy.
    assert mad_std(output['photoz'] - output['redshift_true']) < 0.1
