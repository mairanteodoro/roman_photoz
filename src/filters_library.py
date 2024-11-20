from pathlib import Path

import pandas as pd
import requests

# Base URL for the file download
BASE_URL = "https://roman.gsfc.nasa.gov/science/RRI/Roman_effarea_{}.xlsx"

# Default filename with date
DEFAULT_EFFAREA_FILENAME = "src/data/Roman_effarea_20210614.xlsx"


def download_file(url: str, dest: str):
    response = requests.get(url, timeout=30)
    response.raise_for_status()  # Check if the request was successful
    with open(dest, "wb") as file:
        file.write(response.content)


def read_effarea_file(filename: str = None, **kwargs) -> pd.DataFrame:
    if not filename:
        filename = Path(DEFAULT_EFFAREA_FILENAME).resolve()

    # Extract the date from the filename
    date_str = filename.stem.split("_")[-1]

    # Construct the URL using the extracted date
    url = BASE_URL.format(date_str)

    # Download the file if it does not exist
    if not filename.exists():
        download_file(url, filename)

    df = pd.read_excel(filename, **kwargs)
    return df


if __name__ == "__main__":
    data = read_effarea_file(header=1)
    print(data.head())
    print("Done.")
