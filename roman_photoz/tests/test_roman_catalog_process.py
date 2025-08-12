import os
from unittest.mock import MagicMock, patch

import pytest
from astropy.table import Table

from roman_photoz.default_config_file import default_roman_config
from roman_photoz.roman_catalog_process import RomanCatalogProcess


@pytest.fixture
def roman_catalog_process():
    """Create a basic RomanCatalogProcess instance for testing"""
    return RomanCatalogProcess(config_filename=default_roman_config)


class TestRomanCatalogProcess:
    """Test class for the RomanCatalogProcess"""

    def test_init_with_default_model_filename(self):
        """Test initialization with default model filename"""
        rcp = RomanCatalogProcess(config_filename=default_roman_config)
        assert rcp.model_filename == "roman_model.pkl"
        assert "roman_model.pkl" in rcp.informer_model_path

    def test_init_with_custom_model_filename(self):
        """Test initialization with custom model filename"""
        custom_model = "custom_model.pkl"
        rcp = RomanCatalogProcess(
            config_filename=default_roman_config, model_filename=custom_model
        )
        assert rcp.model_filename == custom_model
        assert custom_model in rcp.informer_model_path

    @pytest.mark.parametrize("file_exists, expected", [(True, True), (False, False)])
    @patch("os.path.exists")
    def test_informer_model_exists(self, mock_path_exists, file_exists, expected):
        """Test the informer_model_exists property with different file existence states"""
        mock_path_exists.return_value = file_exists
        rcp = RomanCatalogProcess(config_filename=default_roman_config)
        assert rcp.informer_model_exists is expected

    @patch("roman_photoz.roman_catalog_process.LephareInformer")
    def test_create_informer_stage_uses_correct_model(self, mock_informer):
        """Test that create_informer_stage uses the correct model path"""
        # Setup the mock
        mock_stage = MagicMock()
        mock_informer.make_stage.return_value = mock_stage

        # Create RCP with custom model
        custom_model = "special_model.pkl"
        rcp = RomanCatalogProcess(
            config_filename=default_roman_config, model_filename=custom_model
        )

        # Add required attributes for create_informer_stage
        rcp.flux_cols = ["flux_F158"]
        rcp.flux_err_cols = ["flux_err_F158"]
        rcp.data = {}

        # Call the method
        rcp.create_informer_stage()

        # Check that the correct model path was used
        call_args = mock_informer.make_stage.call_args[1]
        assert custom_model in call_args["model"]

        # Check that inform was called
        mock_stage.inform.assert_called_once()

    @patch("argparse.ArgumentParser.parse_args")
    @patch("roman_photoz.roman_catalog_process.RomanCatalogProcess")
    def test_main_function_passes_correct_args(self, mock_rcp_class, mock_parse_args):
        """Test that the main() function in the roman_catalog_process.py module
        is initialized correctly and that it correctly passes command-line
        arguments to the RomanCatalogProcess class and its methods"""
        from roman_photoz.roman_catalog_process import main

        # Setup mock args
        mock_args = MagicMock()
        mock_args.config_filename = ""
        mock_args.model_filename = "test_model.pkl"
        mock_args.input_path = "test_path"
        mock_args.input_filename = "test_input.asdf"
        mock_args.output_path = "test_output_path"
        mock_args.output_filename = "test_output.asdf"
        mock_args.output_format = "parquet"
        mock_args.save_results = True
        mock_args.fit_colname = "segment_{}_flux"
        mock_args.fit_err_colname = "segment_{}_flux_err"
        mock_parse_args.return_value = mock_args

        # Setup mock rcp instance
        mock_rcp = MagicMock()
        mock_rcp_class.return_value = mock_rcp

        # Call main
        main()

        # Check that RomanCatalogProcess was initialized with the correct model_filename
        mock_rcp_class.assert_called_once_with(
            config_filename=mock_args.config_filename,
            model_filename=mock_args.model_filename,
        )

        # Check that process was called with the correct arguments
        mock_rcp.process.assert_called_once_with(
            input_filename=mock_args.input_filename,
            output_filename=mock_args.output_filename,
            output_format=mock_args.output_format,
            fit_colname=mock_args.fit_colname,
            fit_err_colname=mock_args.fit_err_colname,
        )

    @pytest.mark.parametrize(
        "model_exists, should_create_informer",
        [
            (
                False,
                True,
            ),  # When model doesn't exist, create_informer_stage should be called
            (
                True,
                False,
            ),  # When model exists, create_informer_stage should NOT be called
        ],
    )
    @patch("os.path.exists")
    @patch(
        "roman_photoz.roman_catalog_process.RomanCatalogProcess.create_informer_stage"
    )
    @patch(
        "roman_photoz.roman_catalog_process.RomanCatalogProcess.create_estimator_stage"
    )
    def test_process_model_existence(
        self,
        mock_create_estimator,
        mock_create_informer,
        mock_exists,
        model_exists,
        should_create_informer,
    ):
        """Test that the process method handles model existence correctly"""
        # Setup mock to indicate model existence
        mock_exists.return_value = model_exists

        # Create RCP instance
        rcp = RomanCatalogProcess(config_filename=default_roman_config)

        # Mock get_data and format_data
        rcp.get_data = MagicMock(return_value=Table())
        rcp.format_data = MagicMock()
        rcp.update_input = MagicMock()

        # Call process method
        rcp.process(input_filename='test')

        # Verify create_informer_stage was called or not based on model existence
        if should_create_informer:
            mock_create_informer.assert_called_once()
        else:
            mock_create_informer.assert_not_called()

        # Verify create_estimator_stage was always called
        mock_create_estimator.assert_called_once()

    @pytest.mark.parametrize(
        "model_filename, env_settings, expected_dirname",
        [
            # Test with default filename and different INFORMER_MODEL_PATH values
            (
                "roman_model.pkl",
                {"INFORMER_MODEL_PATH": "/mock/informer/model/path"},
                "/mock/informer/model/path",
            ),
            (
                "roman_model.pkl",
                {"INFORMER_MODEL_PATH": "/another/mock/path"},
                "/another/mock/path",
            ),
            # Test with custom filenames and different INFORMER_MODEL_PATH values
            (
                "custom_model.pkl",
                {"INFORMER_MODEL_PATH": "/mock/informer/model/path"},
                "/mock/informer/model/path",
            ),
            (
                "special_model.pkl",
                {"INFORMER_MODEL_PATH": "/another/mock/path"},
                "/another/mock/path",
            ),
            # Test fallback to LEPHAREWORK when INFORMER_MODEL_PATH is not set
            (
                "roman_model.pkl",
                {"LEPHAREWORK": "/lepharework/path"},
                "/lepharework/path",
            ),
            (
                "custom_model.pkl",
                {"LEPHAREWORK": "/lepharework/path"},
                "/lepharework/path",
            ),
            # Test default behavior when neither env var is set (empty path)
            ("roman_model.pkl", {}, ""),
            ("custom_model.pkl", {}, ""),
        ],
    )
    def test_informer_model_path(
        self, monkeypatch, model_filename, env_settings, expected_dirname
    ):
        """Test that informer_model_path property correctly combines path and filename.

        The test verifies:
        1. Correct use of INFORMER_MODEL_PATH when set
        2. Fallback to LEPHAREWORK when INFORMER_MODEL_PATH is not set
        3. Proper path combination with different model filenames
        """
        # Save original environment variables
        original_env = {}
        for var in ["INFORMER_MODEL_PATH", "LEPHAREWORK"]:
            if var in os.environ:
                original_env[var] = os.environ[var]
                monkeypatch.delenv(var)

        try:
            # Set environment variables according to test case
            for var, value in env_settings.items():
                monkeypatch.setenv(var, value)

            # Initialize RomanCatalogProcess with the test model filename
            rcp = RomanCatalogProcess(model_filename=model_filename)

            # Check both components of the path
            expected_path = os.path.join(expected_dirname, model_filename)
            assert rcp.informer_model_path == expected_path, (
                f"Full path does not match. Expected: {expected_path}"
            )

            # Verify the directory part matches expected_dirname
            path_dirname = os.path.dirname(rcp.informer_model_path)
            assert path_dirname == expected_dirname, (
                f"Directory part does not match. Expected: {expected_dirname}"
            )

            # Verify the filename part matches model_filename
            path_basename = os.path.basename(rcp.informer_model_path)
            assert path_basename == model_filename, (
                f"Filename part does not match. Expected: {model_filename}"
            )

        finally:
            # Restore original environment variables
            for var in ["INFORMER_MODEL_PATH", "LEPHAREWORK"]:
                if var in original_env:
                    monkeypatch.setenv(var, original_env[var])
                elif var in os.environ:
                    monkeypatch.delenv(var)
