from unittest.mock import patch

import numpy as np
import pytest
from astropy.table import Table
import os

from roman_photoz.roman_catalog_handler import RomanCatalogHandler

TEST_CATALOG_NAME = "test_catalog.parquet"


@pytest.fixture
def mock_catalog_data(roman_catalog_handler, tmp_path):
    """Create mock catalog data for testing"""
    # Get the actual filter names used by the handler
    filter_names = [
        x.replace("roman_", "").lower() for x in roman_catalog_handler.filter_names
    ]

    # Create fields dynamically based on actual filter names
    field_list = [("label", "i4")]
    for name in filter_names:
        field_name = f"segment_{name}_flux"
        field_err_name = f"segment_{name}_flux_err"
        field_list.append((field_name, "f8"))
        field_list.append((field_err_name, "f8"))

    field_list.extend([("redshift", "f8")])

    dt = np.dtype(field_list)

    # Create sample data
    data = np.zeros(3, dtype=dt)
    data["label"] = [1, 2, 3]
    data["redshift"] = [0.5, 1.0, 1.5]

    # Add test values for each filter field
    for i, name in enumerate(filter_names):
        field_name = f"segment_{name}_flux"
        field_err_name = f"segment_{name}_flux_err"
        data[field_name] = [100.0 + i * 10, 150.0 + i * 10, 200.0 + i * 10]
        data[field_err_name] = [5.0 + i * 0.5, 7.5 + i * 0.5, 10.0 + i * 0.5]

    return Table(data)


@pytest.fixture
def roman_catalog_handler():
    """Create a basic RomanCatalogHandler instance for testing"""
    return RomanCatalogHandler()


class TestRomanCatalogHandler:
    """Test class for the RomanCatalogHandler"""

    def test_init_default(self):
        """Test initialization with default parameters"""
        handler = RomanCatalogHandler()
        assert handler.cat_name == ""
        assert handler.cat_array is None
        assert handler.catalog is None
        assert handler.cat_temp_filename == "cat_temp_file.csv"
        assert isinstance(handler.filter_names, list)
        assert len(handler.filter_names) > 0

    def test_init_with_catalog(self, mock_catalog_data, tmp_path):
        """Test initialization with a catalog name"""
        catalog_name = tmp_path / TEST_CATALOG_NAME
        mock_catalog_data.write(catalog_name, format="parquet")
        handler = RomanCatalogHandler(catalog_name)
        assert handler.cat_name == catalog_name

    def test_init_filter_list_none(self):
        """Test initialization when filter list is None"""
        with patch(
            "roman_photoz.utils.roman_photoz_utils.default_roman_config"
        ) as mock_config:
            mock_config.get.return_value = None
            with pytest.raises(
                ValueError, match="Filter list not found in default config file"
            ):
                RomanCatalogHandler()

    def test_read_catalog(self, mock_catalog_data, tmp_path):
        """Test reading a catalog file"""
        # Setup mock
        catalog_name = tmp_path / TEST_CATALOG_NAME
        mock_catalog_data.write(catalog_name, format="parquet")
        handler = RomanCatalogHandler(catalog_name)

        # Check that the catalog was read correctly
        # It's called once in init
        assert handler.cat_array is not None
        assert len(handler.cat_array) == 3
        assert handler.cat_array["label"][0] == 1

    def test_format_catalog(self, roman_catalog_handler, mock_catalog_data):
        """Test formatting a catalog"""
        # Setup
        roman_catalog_handler.cat_array = mock_catalog_data.as_array()

        # Execute
        roman_catalog_handler.format_catalog()

        # Check that the catalog was formatted correctly
        assert roman_catalog_handler.catalog is not None
        assert "label" in roman_catalog_handler.catalog.dtype.names

        # Check that filter fields were added correctly
        for filter_name in roman_catalog_handler.filter_names:
            flux_field = f"segment_{filter_name}_flux"
            flux_err_field = f"segment_{filter_name}_flux_err"
            assert flux_field in roman_catalog_handler.catalog.dtype.names
            assert flux_err_field in roman_catalog_handler.catalog.dtype.names

        # Check that additional required fields were added
        assert "redshift" in roman_catalog_handler.catalog.dtype.names

        # Check that data was copied correctly for a sample field
        assert (
            roman_catalog_handler.catalog["label"][0] == mock_catalog_data["label"][0]
        )
        assert (
            roman_catalog_handler.catalog["redshift"][1] == mock_catalog_data["redshift"][1]
        )


if __name__ == "__main__":
    pytest.main(["-v", "test_roman_catalog_handler.py"])
