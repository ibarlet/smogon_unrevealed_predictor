# A series of functions to pull the needed files from the smogon stats repo automatically
# These will be pulled when the GUI calls a refresh task
# Apparently Windows Defender hats multi-line strings, so docstrings are as comments

import os
import re
from typing import Optional

import pandas as pd
import requests

BASE_PATH = "https://www.smogon.com/stats/"


def read_stats_page():
    """
    Parses the smogon stats page to see all available subfolders
    Performance depends on the structure of the stats page and may need to be updated if that page is reformatted
    :return: DataFrame with columns "Link" and "Upload Date
    """
    stats_page = pd.read_fwf(BASE_PATH, skiprows=3)
    stats_page.columns = [
        "Link",
        "Upload Date",
        "Unnamed: 1",
        "Unnamed: 2",
        "Unnamed:3",
    ]
    stats_page = stats_page[["Link", "Upload Date"]]
    stats_page["Upload Date"] = pd.to_datetime(stats_page["Upload Date"])
    stats_page = stats_page.dropna()

    return stats_page


def determine_available_formats(
    stats_page,
    months_back: int = 12,
    chaos_options: Optional[pd.DataFrame] = None,
    save_to_pickle: bool = False,
):
    """
    Check what formats are avaiable in the recent monthly uploads.
    If no chaos_options are provided, it will check the last 12 months.
    If chaos_options are provided, it will check the months since the last upload in the chaos_options.
    :param stats_page: DataFrame with columns "Link" and "Upload Date"
    :param months_back: Number of months to check back for available formats
    :param chaos_options: DataFrame with columns "Link", "Upload Date", "Size", "Date Link", "Generation", "ELO Floor", "Tier"
    :param save_to_pickle: Save the DataFrame to a pickle file
    """
    if chaos_options is None:
        more_recent_months = months_back
        chaos_options = pd.DataFrame()
        check_range = range(-1 * more_recent_months, 0)
    else:
        # Add 1 day buffer b/c stats page includes the time of day and the chaos_options doesn't
        more_recent_months = (
            stats_page["Upload Date"]
            > chaos_options["Upload Date"].max() + pd.Timedelta(days=1)
        ).sum()
        if more_recent_months == 0:
            return chaos_options, more_recent_months
        check_range = range(-1 * more_recent_months, 0)
    for recent_run_index in check_range:
        mr_link = stats_page.iloc[recent_run_index]["Link"]
        mr_link_path = re.split(r"[<>]", mr_link)[2]
        chaos_subset = pd.read_csv(
            BASE_PATH + mr_link_path + "chaos/", skiprows=4, names=["Text"]
        )
        chaos_subset = pd.DataFrame(
            chaos_subset["Text"].apply(lambda x: re.split(r"[<>\s]+", x)).tolist()
        ).dropna()
        chaos_subset = chaos_subset.rename(
            columns={3: "Link", 5: "Upload Date", 6: "Upload Time", 7: "Size"}
        )[["Link", "Upload Date", "Size"]]
        chaos_subset["Date Link"] = mr_link_path
        chaos_subset = chaos_subset[chaos_subset["Link"].str.contains(".gz")]
        # .gz files weren't available until June 2024. Skip if no .gz files are present
        if len(chaos_subset) == 0:
            continue
        # TODO: This will break when Generation 10 is added.
        # How it will break will depend on how they handle it (i.e. Gen01 through Gen10 or Gen1 through Gen10)
        # Perhaps a regex on all numeric values would be better, would need to address the VGC formats with a year though
        chaos_subset["Generation"] = chaos_subset["Link"].apply(lambda x: int(x[3]))
        chaos_subset = chaos_subset[chaos_subset["Generation"] <= 4]
        chaos_subset["ELO Floor"] = chaos_subset["Link"].apply(
            lambda x: re.split(r"[-.]", x)[1]
        )
        chaos_subset["Tier"] = chaos_subset["Link"].apply(
            lambda x: re.split(r"[-.]", x)[0][4:]
        )
        chaos_subset["Upload Date"] = pd.to_datetime(chaos_subset["Upload Date"])
        chaos_subset["Size"] = chaos_subset["Size"].astype(float)

        chaos_options = pd.concat([chaos_options, chaos_subset])

    # Remove outdated information from formats that have multiple entries
    chaos_options = chaos_options.sort_values(
        by=["Upload Date", "Generation", "Tier", "ELO Floor"],
        ascending=True,
        ignore_index=True,
    )
    chaos_options = chaos_options.drop_duplicates(
        subset=["Generation", "ELO Floor", "Tier"], keep="last"
    )

    if save_to_pickle:
        chaos_options.to_pickle(
            os.path.join("data", "Smogon_Stats", "available_formats.pkl.gz")
        )

    return chaos_options, more_recent_months


def download_files(options: pd.DataFrame, generation, tier, elo_floor):
    """
    Among all the avaiable formats, subset the ones that are needed and download the chaos.json.gz and leads.txt.gz files
    :param options: DataFrame with columns "Link", "Upload Date", "Size", "Date Link", "Generation", "ELO Floor", "Tier"
    :param formats: List of tuples with the format (Generation, Tier, ELO Floor)
    """

    options_subset = options[
        (options["Generation"] == generation)
        & (options["Tier"] == tier)
        & (options["ELO Floor"] == elo_floor)
    ].iloc[0]
    download_chaos(options_subset["Date Link"], options_subset["Link"])
    download_leads(options_subset["Date Link"], options_subset["Link"])


def download_chaos(date_link: str, link: str):
    """Download the chaos.json.gz file for a given month/format"""
    url = BASE_PATH + date_link + "chaos/" + link
    local_filename = os.path.join("data", "Smogon_Stats", "chaos", link)
    os.makedirs(os.path.dirname(local_filename), exist_ok=True)
    response = requests.get(url)
    with open(local_filename, "wb") as f:
        f.write(response.content)


def download_leads(date_link: str, link: str):
    """Download the leads.txt.gz file for a given month/format"""
    url = BASE_PATH + date_link + "leads/" + link.replace("json", "txt")
    local_filename = os.path.join(
        "data",
        "Smogon_Stats",
        "leads",
        link.replace("json", "txt"),
    )
    os.makedirs(os.path.dirname(local_filename), exist_ok=True)
    response = requests.get(url)
    with open(local_filename, "wb") as f:
        f.write(response.content)


def clear_downloaded_files(folders=["chaos", "leads"]):
    """Clear all downloaded files"""
    for folder in folders:
        for file in os.listdir(os.path.join("data", "Smogon_Stats", folder)):
            os.remove(os.path.join("data", "Smogon_Stats", folder, file))
