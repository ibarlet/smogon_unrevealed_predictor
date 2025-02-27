# Functions to build the dataframes from the raw text files
import gzip
import json
import os
import sys

import pandas as pd


def resource_path(relative_path):
    """
    Get the absolute path to the resource, works for dev and for PyInstaller
    Because this file is within data/ you can ignore the data/ in these resource paths
    """
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def read_leads_file(format: str) -> pd.DataFrame:
    lead_file_path = resource_path(f"data/Smogon_Stats/leads/{format}.txt.gz")
    leads = pd.read_csv(
        lead_file_path,
        header=2,
        delimiter="|",
    )
    leads.columns = leads.columns.str.strip()
    leads = leads[["Rank", "Pokemon", "Usage %", "Raw"]].dropna()
    leads["Pokemon"] = leads["Pokemon"].str.strip()
    leads = leads.rename(
        columns={"Usage %": "Lead Usage", "Rank": "Lead Rank", "Raw": "Lead Count"},
    )
    return leads


def read_chaos_file(format: str) -> dict:
    chaos_file_path = resource_path(f"data/Smogon_Stats/chaos/{format}.json.gz")
    with gzip.open(chaos_file_path, mode="r") as f:
        data = json.loads(f.read().decode("utf-8"))
    return data


def get_raw_counts_df(chaos_file: dict) -> pd.DataFrame:
    raw_counts = {
        pokemon: data["Raw count"] for pokemon, data in chaos_file["data"].items()
    }
    counts_df = pd.DataFrame.from_dict(raw_counts, orient="index", columns=["Raw"])

    rates = counts_df["Raw"] / counts_df["Raw"].sum()

    return counts_df, rates


def add_lead_information(
    lead_df: pd.DataFrame, counts_df: pd.DataFrame
) -> pd.DataFrame:
    counts_df = counts_df.join(lead_df.set_index("Pokemon"), how="left").fillna(0)
    counts_df["Non Lead Count"] = counts_df["Raw"] - counts_df["Lead Count"]
    counts_df["Non Lead Multiplier"] = counts_df["Non Lead Count"] / counts_df["Raw"]

    return counts_df


def get_teammates_df(chaos_file: dict, normalize=True) -> pd.DataFrame:
    teammates = {
        pokemon: data["Teammates"] for pokemon, data in chaos_file["data"].items()
    }
    teammates_df = pd.DataFrame.from_dict(teammates, orient="index").fillna(0)

    if normalize:
        # Normalizes the data by dividing by the column frequency
        # So teammates_df['Skarmory']['Zapdos'] is P(Zapdos | Skarmory)
        teammates_df = teammates_df.div(teammates_df.sum(axis=0), axis=1)

    return teammates_df


def get_checks_df(chaos_file: dict) -> pd.DataFrame:
    check_dict = {
        pokemon: data["Checks and Counters"]
        for pokemon, data in chaos_file["data"].items()
    }
    check_dict_df = pd.DataFrame.from_dict(check_dict, orient="columns")
    # check_encounters_df = check_dict_df.map(
    #     lambda x: x[0] if isinstance(x, list) else 0
    # )
    check_rate_df = check_dict_df.map(lambda x: x[1] if isinstance(x, list) else 0)
    # check_rate_std_df = check_dict_df.map(lambda x: x[2] if isinstance(x, list) else 0)

    return check_rate_df
