# -*- coding: utf-8 -*-
"""
Created on Tue Sep 30 10:07:13 2025

@author: antony.praderva
"""

# visualize_collection.py
import streamlit as st
import pandas as pd
import plotly.express as px
from collection_dump import fetch_all_releases, USERNAME

st.set_page_config(page_title="Discogs Collection Dashboard", layout="wide")

st.title("📀 My Discogs Collection Dashboard")

# Fetch collection
with st.spinner("Fetching data from Discogs API..."):
    df = fetch_all_releases(USERNAME)

# Parse dates
df["added"] = pd.to_datetime(df["added"], errors="coerce")

# Sidebar filters
st.sidebar.header("Filters")
all_genres = sorted(set(g for g in df["genres"].dropna().str.split(", ").explode()))
all_styles = sorted(set(s for s in df["styles"].dropna().str.split(", ").explode()))

selected_genre = st.sidebar.selectbox("Filter by Genre", options=["All"] + all_genres)
selected_style = st.sidebar.selectbox("Filter by Style", options=["All"] + all_styles)

df_filtered = df.copy()
if selected_genre != "All":
    df_filtered = df_filtered[df_filtered["genres"].str.contains(selected_genre, na=False)]
if selected_style != "All":
    df_filtered = df_filtered[df_filtered["styles"].str.contains(selected_style, na=False)]

st.success(f"Loaded {len(df_filtered)} records (after filtering)")
# ==========================
# Records by Year
# ==========================
st.subheader("📅 Records by Year")

# Clean up year column
df_filtered["year"] = pd.to_numeric(df_filtered["year"], errors="coerce")
df_year = df_filtered[df_filtered["year"] > 0]  # ignore 0 and negatives

df_year = df_year["year"].value_counts().sort_index().reset_index()
df_year.columns = ["Year", "Count"]

if df_year.empty:
    st.warning("No valid release years found in your collection.")
else:
    fig_year = px.bar(df_year, x="Year", y="Count", title="Records by Year")
    st.plotly_chart(fig_year, use_container_width=True)


# ==========================
# Top Styles
# ==========================
st.subheader("🎼 Top Styles")
df_styles = (
    df_filtered["styles"]
    .dropna()
    .str.split(", ")
    .explode()
    .value_counts()
    .head(15)
    .reset_index()
)
df_styles.columns = ["Style", "Count"]

fig_styles = px.bar(df_styles, x="Style", y="Count", title="Top 15 Styles")
st.plotly_chart(fig_styles, use_container_width=True)

# ==========================
# Growth Over Time
# ==========================
st.subheader("📈 Collection Growth Over Time")

# Ensure "added" is datetime
df_filtered["added"] = pd.to_datetime(df_filtered["added"], errors="coerce")

# Drop rows with no valid date
df_time = df_filtered.dropna(subset=["added"]).set_index("added").sort_index()

if df_time.empty:
    st.warning("No valid 'added' dates found in your collection.")
else:
    monthly_adds = df_time.resample("M").size()
    cumulative = monthly_adds.cumsum()

    df_growth = pd.DataFrame({
        "Month": monthly_adds.index,
        "New records": monthly_adds.values,
        "Cumulative": cumulative.values
    })

    fig_growth = px.line(
        df_growth,
        x="Month",
        y=["New records", "Cumulative"],
        title="Discogs Collection Growth Over Time"
    )
    st.plotly_chart(fig_growth, use_container_width=True)


# ==========================
# Raw Data Preview
# ==========================
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))


