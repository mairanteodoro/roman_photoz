from pathlib import Path

import pandas as pd
import requests

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


def create_filter_files(data: pd.DataFrame, filepath: str = "") -> None:
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
    path = Path(".").resolve() if filepath is None else Path(filepath).resolve()
    wave = data.columns[0]
    for col in data.columns[1:]:
        output_data = data[[wave, col]]
        # convert wavelength unit from um to A
        output_data[wave] = output_data[wave] * 1e4
        filename = "roman" + "_".join(col.split(" ")).strip() + ".pb"
        first_line = f"# {col} (Roman filter info obtained from {BASE_URL.format(DEFAULT_FILE_DATE)})"
        fq_path = path / filename
        with open(fq_path, "w") as f:
            f.write(first_line + "\n")
            output_data.to_csv(f, sep=" ", index=False, header=False, mode="a")


if __name__ == "__main__":

    # create dataframe from file
    data = read_effarea_file(header=1)

    # format and create files to be used by rail+lephare
    create_filter_files(data=data)

    print("Done.")
