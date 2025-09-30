# visualize_collection.py
import streamlit as st
import pandas as pd
import plotly.express as px
import random
from collection_dump import fetch_all_releases

USERNAME = st.secrets["DISCOGS_USERNAME"]

st.set_page_config(page_title="Discogs Collection Dashboard", layout="wide")
st.title("📀 My Discogs Collection Dashboard")

# --------------------------
# Cached fetch
# --------------------------
@st.cache_data(show_spinner="Fetching data from Discogs API...")
def load_collection(username):
    return fetch_all_releases(username)

# Load once (cached)
df = load_collection(USERNAME).copy()

# Parse dates safely
df["added"] = pd.to_datetime(
    df["added"],
    errors="coerce",
    utc=True,
    infer_datetime_format=True
)

# --------------------------
# Sidebar filters
# --------------------------
df_filtered=df
def parse_duration(duration_str):
    """Convert Discogs duration string (MM:SS or HH:MM:SS) into seconds."""
    if not isinstance(duration_str, str) or not duration_str.strip():
        return 0
    parts = duration_str.split(":")
    try:
        parts = [int(p) for p in parts]
        if len(parts) == 2:  # MM:SS
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:  # HH:MM:SS
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        else:
            return 0
    except Exception:
        return 0

# --------------------------
# Quick Synthesis / Stats
# --------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("🎵 Total Records", f"{len(df_filtered):,}")

with col2:
    unique_artists = df_filtered["artists"].nunique()
    st.metric("👨‍🎤 Unique Artists", f"{unique_artists:,}")

with col3:
    years = pd.to_numeric(df_filtered["year"], errors="coerce")
    years = years[years > 0]  # ignore 0 or invalid
    if not years.empty:
        st.metric("📅 Year Range", f"{int(years.min())} - {int(years.max())}")
    else:
        st.metric("📅 Year Range", "N/A")


with col4:
    if "labels" in df_filtered.columns and not df_filtered["labels"].dropna().empty:
        # Split multiple labels, clean, and count
        all_labels = (
            df_filtered["labels"]
            .dropna()
            .str.split(", ")
            .explode()
            .str.replace(r"\s*\(\d+\)$", "", regex=True)  # remove (5), (6) etc.
            .str.strip()
        )
        top_label = all_labels.value_counts().idxmax()
        top_count = all_labels.value_counts().max()
        st.metric("🏆 Favourite Label", f"{top_label} ({top_count})")
    else:
        st.metric("🏆 Favourite Label", "N/A")
# --------------------------
# Records by Year
# --------------------------
st.subheader("📅 Records by Year")
df_filtered["year"] = pd.to_numeric(df_filtered["year"], errors="coerce")
df_year = df_filtered[df_filtered["year"] > 0]

df_year = df_year["year"].value_counts().sort_index().reset_index()
df_year.columns = ["Year", "Count"]

if df_year.empty:
    st.warning("No valid release years found in your collection.")
else:
    max_year = df_year.loc[df_year["Count"].idxmax(), "Year"]
    df_year["Category"] = df_year["Year"].apply(lambda y: "Max" if y == max_year else "Other")

    fig_year = px.bar(
        df_year,
        x="Year",
        y="Count",
        color="Category",
        title="Records by Year",
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig_year.update_layout(showlegend=False)
    st.plotly_chart(fig_year, use_container_width=True)

# --------------------------
# Top Styles
# --------------------------
st.subheader("🎼 Top Styles")

def clean_styles(row):
    if pd.isna(row):
        return None
    styles = [s.strip() for s in row.split(",")]
    if "Black Metal" in styles:
        more_specific = [s for s in styles if s != "Black Metal" and s.endswith("Black Metal")]
        if more_specific:
            styles = [s for s in styles if s != "Black Metal"]
    return styles

df_styles = (
    df_filtered["styles"]
    .dropna()
    .apply(clean_styles)
    .dropna()
    .explode()
    .value_counts()
    .head(15)
    .reset_index()
)
df_styles.columns = ["Style", "Count"]

if df_styles.empty:
    st.warning("No valid styles found in your collection.")
else:
    df_styles = df_styles.sort_values("Count", ascending=True)
    max_style = df_styles.loc[df_styles["Count"].idxmax(), "Style"]
    df_styles["Category"] = df_styles["Style"].apply(lambda s: "Max" if s == max_style else "Other")

    fig_styles = px.bar(
        df_styles,
        x="Count",
        y="Style",
        orientation="h",
        color="Category",
        title="Top 15 Styles",
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig_styles.update_layout(showlegend=False)
    st.plotly_chart(fig_styles, use_container_width=True)

# ---------------------
# Pressing Types (Proportions)
# ---------------------
st.subheader("📀 Pressing Types in Collection")

pressing_counts = {
    "Original Press": int(df_filtered["is_original"].sum()),
    "Repress/Reissue": int(df_filtered["is_reissue"].sum()),
    "Limited Edition": int(df_filtered["is_limited"].sum()),
}
total = sum(pressing_counts.values())

df_pressing = pd.DataFrame(
    [(k, v, (v / total * 100 if total > 0 else 0)) for k, v in pressing_counts.items()],
    columns=["Type", "Count", "Percent"]
)

if df_pressing.empty or total == 0:
    st.warning("No pressing type info available.")
else:
    df_pressing = df_pressing.sort_values("Percent", ascending=True)
    max_type = df_pressing.loc[df_pressing["Percent"].idxmax(), "Type"]
    df_pressing["Category"] = df_pressing["Type"].apply(lambda t: "Max" if t == max_type else "Other")

    fig_pressing = px.bar(
        df_pressing,
        x="Percent",
        y="Type",
        orientation="h",
        color="Category",
        text=df_pressing["Percent"].map("{:.1f}%".format),
        title="Proportion of Pressing Types (%)",
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig_pressing.update_traces(textposition="outside")
    fig_pressing.update_layout(showlegend=False, xaxis_title="Percent (%)")
    st.plotly_chart(fig_pressing, use_container_width=True)

# --------------------------
# Growth Over Time
# --------------------------
st.subheader("📈 Collection Growth Over Time")

missing_added = df_filtered["added"].isna().sum()
df_time = df_filtered.dropna(subset=["added"]).set_index("added").sort_index()

if df_time.empty:
    st.warning("No valid 'date_added' found in your collection.")
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
        title=f"Discogs Collection Growth Over Time "
              f"(showing {len(df_time)} / {len(df_filtered)} records)",
        color_discrete_map={"New records": "#3498db", "Cumulative": "#e74c3c"}
    )
    st.plotly_chart(fig_growth, use_container_width=True)

    if missing_added > 0:
        st.info(f"⚠️ {missing_added} records had no parseable 'date_added' "
                f"and are excluded from the growth chart.")
import re

def clean_name(name):
    """Remove trailing disambiguation like ' (5)' from Discogs names."""
    if not isinstance(name, str):
        return name
    return re.sub(r"\s*\(\d+\)$", "", name).strip()

import requests

DISCOGS_API_BASE = "https://api.discogs.com"

def fetch_release_videos(release_id):
    """Fetch video links from Discogs release API."""
    url = f"{DISCOGS_API_BASE}/releases/{release_id}"
    try:
        r = requests.get(url)
        r.raise_for_status()
        data = r.json()
        videos = data.get("videos", [])
        return [{"title": v.get("title"), "uri": v.get("uri")} for v in videos]
    except Exception as e:
        st.warning(f"Could not fetch videos for release {release_id}: {e}")
        return []
# --------------------------
# Random Album in Sidebar
# --------------------------

# Ensure we have album covers available
if "all_covers" not in st.session_state:
    st.session_state.all_covers = df.dropna(subset=["cover_url"])

col1, col2 = st.sidebar.columns([5, 1])
with col1:
    st.markdown("### 🎨 Random Album")
with col2:
    if st.button("🔄", key="reload_album"):
        st.session_state.random_album = None

# Pick or refresh random album
if "random_album" not in st.session_state or st.session_state.random_album is None:
    st.session_state.random_album = st.session_state.all_covers.sample(1).iloc[0]


album = st.session_state.random_album

# Clean fields
def clean_name(value):
    if not value or str(value).lower() == "nan":
        return "Unknown"
    # If multiple names (list-like), join them
    if isinstance(value, (list, tuple)):
        return " / ".join(str(v).split(" (")[0] for v in value)
    return str(value).split(" (")[0]  # strip (5), (6)

cover_url = album.get("cover_url", "")
release_id = album.get("release_id", "")
artist = clean_name(album.get("artists", album.get("artist", "Unknown")))
title = album.get("title", "Unknown")
label = clean_name(album.get("labels", album.get("label", "Unknown")))
year = album.get("year", "Unknown")
videos = album.get("videos", [])  # expect list of dicts

link = f"https://www.discogs.com/release/{release_id}"

# Album info block
st.sidebar.markdown(
    f"""
    <div style="text-align:center;">
        <a href="{link}" target="_blank">
            <img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.2);"/>
        </a>
        <p><b>{artist}</b><br>{title}<br>
        <span style="color:gray; font-size:90%;">{label}, {year}</span></p>
    </div>
    """,
    unsafe_allow_html=True
)


 # Fetch videos
videos = fetch_release_videos(release_id)
if videos:
    st.sidebar.markdown("#### 🎥 Videos")
    for v in videos:
        uri = v.get("uri")
        if "youtube.com" in uri or "youtu.be" in uri:
            st.sidebar.video(uri)
        else:
            st.sidebar.markdown(f"- [{v.get('title')}]({uri})")

# Style reload button (no gray box)
st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        background: none !important;
        border: none !important;
        color: #e74c3c !important;
        font-size: 20px !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
    }
    div.stButton > button:first-child:hover {
        color: #c0392b !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# --------------------------
# Data Preview
# --------------------------
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))























