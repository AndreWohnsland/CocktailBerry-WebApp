import os
import time
import datetime
import json
import requests
from requests.exceptions import ConnectTimeout, ReadTimeout, ConnectionError as rConnectionError
import streamlit as st
from streamlit.logger import get_logger
import pandas as pd
from dotenv import load_dotenv

from .models import ReceivedData, CocktailSchema


load_dotenv()
is_dev = os.getenv("DEBUG") is not None
backend_url = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
DATEFORMAT_STR = "%d/%m/%Y, %H:%M"
logger = get_logger(__name__)


def __myround(x, base=5):
    """Rounds to the nearest number to given base"""
    return base * round(x / base)


@st.cache_data(ttl=60)
def generate_df():
    """Gets the data from deta and converts to df"""
    # something in streamlit cloud seems to block the request, so we need to wait a bit
    time.sleep(1)
    cocktails = {}
    try:
        cocktails_response = requests.get(f"{backend_url}/public/cocktails", timeout=30)
        if cocktails_response.ok:
            cocktails = json.loads(cocktails_response.text)
        else:
            logger.warning("Error from backend: %s: %s", cocktails_response.status_code, cocktails_response.text)
    except (ConnectTimeout, ReadTimeout, rConnectionError):
        logger.error("Timeout when connecting to backend.")
    df = pd.DataFrame(cocktails).rename(
        columns={
            ReceivedData.COUNTRYCODE: CocktailSchema.language,
            ReceivedData.MACHINENAME: CocktailSchema.machine_name,
            ReceivedData.COCKTAILNAME: CocktailSchema.cocktail_name,
            ReceivedData.VOLUME: CocktailSchema.volume,
            ReceivedData.RECEIVEDATE: CocktailSchema.receivedate,
        }
    )
    if not df.empty:
        df = df[  # pylint: disable=unsubscriptable-object
            [
                CocktailSchema.language,
                CocktailSchema.machine_name,
                CocktailSchema.cocktail_name,
                CocktailSchema.volume,
                CocktailSchema.receivedate,
            ]
        ]
        df[CocktailSchema.receivedate] = pd.to_datetime(df[CocktailSchema.receivedate], format=DATEFORMAT_STR)
    return df


@st.cache_data(ttl=600)
def get_installation_count():
    try:
        installations = requests.get(f"{backend_url}/public/installations", timeout=30)
        if installations.ok:
            return int(installations.text)
        logger.warning("Error from backend: %s: %s", installations.status_code, installations.text)
    except (ConnectTimeout, ReadTimeout, rConnectionError):
        logger.error("Timeout when connecting to backend.")
    return 0


@st.cache_data(ttl=300)
def filter_dataframe(
    df: pd.DataFrame, countries: list, machines: list, recipes: list, only_one_day: bool, dates: tuple[datetime.date, datetime.date]
):
    """Applies the sidebar filter option to the data"""
    filtered_df = df.loc[
        df[CocktailSchema.language].isin(countries)
        & df[CocktailSchema.machine_name].isin(machines)
        & df[CocktailSchema.cocktail_name].isin(recipes)
        & (df[CocktailSchema.receivedate] >= pd.Timestamp(dates[0]))
        & (df[CocktailSchema.receivedate] <= pd.Timestamp(dates[1]) + pd.Timedelta(days=1))
    ]
    if only_one_day:
        filtering = filtered_df[CocktailSchema.receivedate] >= (datetime.datetime.now() - datetime.timedelta(hours=24))  # type: ignore
        filtered_df = filtered_df[filtering]
    return filtered_df


@st.cache_data(ttl=300)
def sum_volume(df: pd.DataFrame, country_split: bool) -> pd.DataFrame:
    """Aggregate by language and machine Name, returns total volumes and cocktail counts"""
    grouping = [CocktailSchema.machine_name]
    if country_split:
        grouping = [CocktailSchema.language, CocktailSchema.machine_name]
    volumes = (
        df.groupby(grouping)[CocktailSchema.volume]  # type: ignore
        .agg(["sum", "count"])
        .reset_index()
        .sort_values(["sum", "count"], ascending=False)
        .rename(
            columns={
                "sum": CocktailSchema.cocktail_volume,
                "count": CocktailSchema.cocktail_count,
            }
        )
    )
    volumes[CocktailSchema.cocktail_volume] = volumes[CocktailSchema.cocktail_volume] / 1000
    return volumes


@st.cache_data(ttl=300)
def cocktail_count(df: pd.DataFrame, limit_recipe: int, country_split: bool) -> pd.DataFrame:
    """Aggregate by language and cocktail name, limits to x most used recipes"""
    grouping = [CocktailSchema.cocktail_name]
    if country_split:
        grouping = [CocktailSchema.cocktail_name, CocktailSchema.language]
    # first group by the restrictions, this needs to be done in both cases
    cocktails = (
        df.groupby(grouping)[CocktailSchema.volume]  # type: ignore
        .count()
        .reset_index()
        .rename(
            columns={
                CocktailSchema.volume: CocktailSchema.cocktail_count,
            }
        )
    )
    # if no split, the logic is quite simple, just sort and limit them
    if not country_split:
        cocktails.sort_values([CocktailSchema.cocktail_count], ascending=False, inplace=True)
        cocktails = cocktails.iloc[:limit_recipe]
        return cocktails
    # If split by country, for the listing, we need to generate a tmp rank
    # that we can order by that rank for the cocktail name (its dependant on total count)
    name_order = df.groupby([CocktailSchema.cocktail_name])[CocktailSchema.volume].count().sort_values().index.to_list()[-limit_recipe:]
    sorter_index = dict(zip(name_order, range(len(name_order))))
    cocktails["Rank"] = cocktails[CocktailSchema.cocktail_name].map(sorter_index)
    cocktails.sort_values(["Rank", CocktailSchema.cocktail_count], ascending=False, inplace=True)
    cocktails.dropna(axis=0, inplace=True)
    cocktails.drop("Rank", axis=1, inplace=True)
    return cocktails


@st.cache_data(ttl=300)
def time_aggregation(df: pd.DataFrame, hour_grouping: bool, machine_grouping: bool) -> pd.DataFrame:
    """Aggregates the data either by day or hour, depending on the last_day param"""
    freq = "1D"
    if hour_grouping:
        freq = "1h"
    date_grouper = pd.Grouper(key=CocktailSchema.receivedate, freq=freq)
    grouping = [date_grouper]
    if machine_grouping:
        grouping = [date_grouper, CocktailSchema.machine_name]
    time_df = (
        df.groupby(grouping)[CocktailSchema.cocktail_name]  # type: ignore
        .count()
        .reset_index()
        .rename(
            columns={
                CocktailSchema.cocktail_name: CocktailSchema.cocktail_count,
            }
        )
    )
    time_df = time_df[time_df[CocktailSchema.cocktail_count] != 0]
    return time_df


@st.cache_data(ttl=300)
def serving_aggregation(df: pd.DataFrame, machine_split: bool, min_count: int):
    """Aggregates by serving sizes"""
    # rounds to the closest 25
    serving_df = df.copy(deep=True)
    serving_df[CocktailSchema.volume] = serving_df[CocktailSchema.volume].apply(__myround, args=(25,))
    grouping = [CocktailSchema.volume]
    if machine_split:
        grouping = [CocktailSchema.machine_name, CocktailSchema.volume]
    serving_df = (
        serving_df.groupby(grouping)[CocktailSchema.language]  # type: ignore
        .agg(["count"])
        .reset_index()
        .sort_values([CocktailSchema.volume], ascending=True)
        .rename(
            columns={
                "count": CocktailSchema.cocktail_count,
            }
        )
    )
    # for multiple grouping needs to calculate the sum per group and only include the ones having more than min
    serving_size_count = serving_df.groupby(CocktailSchema.volume).sum()
    volumes_to_keep = serving_size_count[serving_size_count[CocktailSchema.cocktail_count] >= min_count].index.to_list()
    return serving_df[serving_df[CocktailSchema.volume].isin(volumes_to_keep)]
