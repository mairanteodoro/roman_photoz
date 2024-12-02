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
    response = requests.get(url, timeout=30)
    # check if the request was successful
    response.raise_for_status()
    with open(dest, "wb") as file:
        file.write(response.content)


def read_effarea_file(filename: str = "", **kwargs) -> pd.DataFrame:
    fname_path = (
        Path(DEFAULT_EFFAREA_FILENAME).resolve()
        if not filename
        else Path(filename).resolve()
    )
    # extract the date from the filename
    date_str = fname_path.stem.split("_")[-1]
    # construct the URL using the extracted date
    url = BASE_URL.format(date_str)
    # download the file if it does not exist
    if not fname_path.exists():
        download_file(url, fname_path.as_posix())
    df = pd.read_excel(fname_path, **kwargs)
    return df


def create_filter_files(data: pd.DataFrame, filepath: str = "") -> None:
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
