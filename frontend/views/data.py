
import pandas as pd
import streamlit as st

from .. import data, plots
from ..models import CocktailSchema

LANGUAGE_SPLIT_DESC = "Split by Language Used"


def display_data(filtered_df: pd.DataFrame, recipes_limit: int, last_day: bool):
    """Generate all the data views (plots and tables) from the data."""
    if filtered_df.empty:
        __say_no_data()
        return
    __show_filtered_size(filtered_df, last_day)
    __show_recipe_data(filtered_df, recipes_limit)
    __show_time_stats(filtered_df, last_day)
    __show_volume_stats(filtered_df)
    __show_serving_size(filtered_df)


def __show_filtered_size(filtered_df: pd.DataFrame, last_day: bool):
    """Also displays some information how much data is left after filtering."""
    amount_cocktails = filtered_df.shape[0]
    cocktail_str = "cocktails" if amount_cocktails != 1 else "cocktail"
    if not last_day:
        st.success(f"After filtering, **{amount_cocktails}** {cocktail_str} remain")
        return
    phrasing = "were" if amount_cocktails != 1 else "was"
    st.success(f"Today, **{amount_cocktails}** {cocktail_str} {phrasing} produced 🥳")


def __show_recipe_data(filtered_df: pd.DataFrame, recipes_limit: int):
    """Display Recipes count by recipe and country."""
    st.header("🧾 Recipes Made")
    country_split = st.checkbox(LANGUAGE_SPLIT_DESC, False, key="country_recipe")
    recipe_df = data.cocktail_count(filtered_df, recipes_limit, country_split)
    plots.generate_recipes_treemap(recipe_df, country_split)
    header_addition = " and Language used" if country_split else ""
    with st.expander(f"[Table] Aggregated by {CocktailSchema.cocktail_name}{header_addition}:"):
        st.table(recipe_df)


def __show_time_stats(filtered_df: pd.DataFrame, last_day: bool):
    """Display Cocktail count over time."""
    st.header("⏱️ Data Over Time")
    hour_grouping, machine_grouping = __define_granularity(last_day)
    time_df = data.time_aggregation(filtered_df, hour_grouping, machine_grouping)
    plots.generate_time_plot(time_df, machine_grouping)


def __show_volume_stats(filtered_df: pd.DataFrame):
    """Lets the user decide to also split by country code."""
    st.header("🍸 Volume and Number of Cocktails")
    country_split = st.checkbox(LANGUAGE_SPLIT_DESC, False, key="country_machine")
    volume_df = data.sum_volume(filtered_df, country_split)
    plots.generate_volume_treemap(volume_df, country_split)
    header_addition = " Language used and" if country_split else ""
    with st.expander(f"[Table] Aggregated by{header_addition} {CocktailSchema.machine_name}:"):
        st.table(volume_df.style.format({CocktailSchema.cocktail_volume: "{:.2f}"}))


def __show_serving_size(filtered_df: pd.DataFrame):
    """Show stats over the prepared volume choices."""
    st.header("🥃 Serving Sizes")
    col1, col2 = st.columns(2)
    machine_split = col1.checkbox("Split by Machine", False, key="serving_machine")
    # only make it available if no machine split is activated
    max_value_possible = 10
    min_servings: int = col2.slider(
        "Filter Minimal Serving Count", 0,
        max_value_possible, 5
    )  # type: ignore
    serving_df = data.serving_aggregation(filtered_df, machine_split, min_servings)
    plots.generate_serving_size_bars(serving_df, machine_split)


def __define_granularity(last_day):
    """Lets the user choose in case of all data to aggregate by hour or day."""
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Different Machines?")
        machine_grouping = st.checkbox("Split by Machine", False)
    if last_day:
        return True, machine_grouping
    grouping_options = ("One Day", "One Hour")
    with col2:
        selected_grouping = st.radio(
            "Select the Time Grouping",
            grouping_options
        )
    hour_grouping = selected_grouping == grouping_options[1]
    return hour_grouping, machine_grouping


def __say_no_data():
    """Display a warning that there is no data to plot."""
    st.warning(
        """
        ⚠️ There is currently no detailed data to be displayed.
        This is probably a result of following reason:

        ❌ Your filtering is too strict and nothing matches the criteria.
        Change your filter or reload the page to reset the filtering.
        """
    )


def display_installations(df: pd.DataFrame):
    """Show the installation data over time and distribution."""
    st.header("📦 Installation Data")
    if df.empty:
        st.info("Currently no installation data available. Maybe it's time to install your onw! ✨")
        return
    st.write("Installation Count over Time")
    os_split = st.checkbox("Split by OS")
    over_time_df = data.cumulate_installations(df, os_split)
    plots.generate_installation_time_chart(over_time_df, os_split)
    st.write("Installation Distribution")
    distribution_df = data.aggregate_installations(df)
    plots.generate_installation_treemap(distribution_df)
    with st.expander("[Table] Installation Distribution"):
        st.table(distribution_df)
