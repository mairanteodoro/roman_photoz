from pathlib import Path
import sys

import pandas as pd
import requests
import os

# import lephare

# date of the file
DEFAULT_FILE_DATE = "20210614"

# Base URL for the file download
BASE_URL = "https://roman.gsfc.nasa.gov/science/RRI/Roman_effarea_{}.xlsx"

# Default filename with date
DEFAULT_EFFAREA_FILENAME = f"src/data/Roman_effarea_{DEFAULT_FILE_DATE}.xlsx"


def download_file(url: str, dest: str):
    """
    Download a file from the specified URL and save it to the destination path.

    Parameters
    ----------
    url : str
        The URL of the file to download.
    dest : str
        The destination path where the file will be saved.
    """
    response = requests.get(url, timeout=30)
    # check if the request was successful
    response.raise_for_status()
    with open(dest, "wb") as file:
        file.write(response.content)


def read_effarea_file(filename: str = "", **kwargs) -> pd.DataFrame:
    """
    Read the efficiency area file into a pandas DataFrame. If the file does not exist,
    it will be downloaded from the specified URL.

    Parameters
    ----------
    filename : str, optional
        The path to the efficiency area file. If not provided, the default filename will be used.
    **kwargs
        Additional keyword arguments to pass to pd.read_excel.

    Returns
    -------
    pd.DataFrame
        The data from the efficiency area file.
    """
    fname_path = (
        Path(DEFAULT_EFFAREA_FILENAME).resolve()
        if not filename
        else Path(filename).resolve()
    )
    # extract the date from the filename
    # (assuming filename format "blah_blah_YYYYMMDD.suffix")
    date_str = fname_path.stem.split("_")[-1]
    # download the file if it does not exist
    if not fname_path.exists():
        # construct the URL using the extracted date
        url = BASE_URL.format(date_str)
        download_file(url, fname_path.as_posix())
    df = pd.read_excel(fname_path, **kwargs)
    return df


def create_files(data: pd.DataFrame, filepath: str = "") -> None:
    """
    Create filter files from the provided DataFrame. Each filter file contains
    wavelength and filter data, with a comment line at the top.

    Parameters
    ----------
    data : pd.DataFrame
        The DataFrame containing the filter data.
    filepath : str, optional
        The path where the filter files will be saved. If not provided, the current directory will be used.
    """
    path = create_path(filepath)
    wave = data.columns[0]
    # Roman phot parameters
    filter_list: list = []
    filter_rep = path

    for col in data.columns[1:]:
        output_data = data[[wave, col]]
        # convert wavelength from um to A
        output_data[wave] = output_data[wave] * 1e4
        filename = "roman" + "_".join(col.split(" ")).strip() + ".pb"
        first_line = f"# {col} (Roman filter info obtained from {BASE_URL.format(DEFAULT_FILE_DATE)})"
        fq_path = path / filename
        with open(fq_path, "w") as f:
            f.write(first_line + "\n")
            output_data.to_csv(f, sep=" ", index=False, header=False, mode="a")
        filter_list.append(filename)

    # create phot.par file to be used with the filter command
    create_roman_phot_par_file(filter_list, filter_rep)


def create_roman_phot_par_file(filter_list: list, filter_rep: Path) -> None:
    f_list: str = ",".join(filter_list)
    f_calib: str = ",".join(len(filter_list) * ["0"])
    f_rep: str = (
        f"{filter_rep.as_posix()}  # Repository in which the filters are stored"
    )
    content = f"""
    ##############################################################################################
    ###########                          FILTERS                                     #############
    ##############################################################################################
    FILTER_REP {f_rep}
    FILTER_LIST {f_list}
    TRANS_TYPE 1
    FILTER_CALIB {f_calib}
    FILTER_FILE filter_roman  # name of file with filters (-> $ZPHOTWORK/filt/)
    """
    filename = filter_rep / "roman_phot.par"
    with open(filename, "w") as f:
        f.write(content)


def create_path(filepath: str = "") -> Path:
    # default to save filter files locally
    path = Path(".").resolve()
    if lepharedir := os.environ.get("LEPHAREDIR", None):
        # save files to the lephare dir
        path = Path(lepharedir, "filt", "roman").resolve()
    elif filepath is not None:
        # save files to custom path
        path = Path(filepath).resolve()
    # create path if they don't exist
    print("Creating directory structure...")
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_filter_command(config_file_path: str = "") -> None:
    from lephare.filter import Filter

    config_file = Path(config_file_path, "roman_phot.par").as_posix()
    filter = Filter(config_file=config_file)
    filter.run()


def run(input_filename, input_path):
    # create dataframe from file
    data = read_effarea_file(filename=input_filename, header=1)
    # format and create files to be used by rail+lephare
    create_files(data=data, filepath=input_path)
    # run filter command to create the filter file needed by rail+lephare
    run_filter_command(config_file_path=input_path)


if __name__ == "__main__":

    # this module takes a filename as input containing
    # the monocromatic effective area of each filter per column
    # and creates one file for each filter as well as
    # the final merged file expected by rail+lephare

    # get path where the results will be saved to
    input_path = sys.argv[1] if len(sys.argv) > 1 else ""
    # get effective area filename
    input_filename = sys.argv[2] if len(sys.argv) > 2 else ""

    run(input_filename=input_filename, input_path=input_path)

    print("Done.")
