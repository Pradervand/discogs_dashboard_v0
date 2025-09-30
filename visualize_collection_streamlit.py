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
# Pressing Types (Unified Icon Block with Sorted Groups + Legend, Centered, Bigger Icons)
# ---------------------
st.subheader("📀 Original Press VS Reissue/Repress")

pressing_counts = {
    "Original Press": int(df_filtered["is_original"].sum()),
    "Repress/Reissue": int(df_filtered["is_reissue"].sum()),
}
total = sum(pressing_counts.values())

icons = {
    "Original Press": "📀",
    "Repress/Reissue": "🔁",
}

ICON_SCALE = 5  # 1 icon = 5%
WRAP = 10      # max icons per line

# Build icon rows
all_rows = []
for press_type, count in pressing_counts.items():
    if total > 0 and count > 0:
        percent = (count / total) * 100
        num_icons = max(1, int(round(percent / ICON_SCALE)))
        icon_block = "".join([icons[press_type]] * num_icons)
        all_rows.append((press_type, percent, icon_block))

# Sort Originals first, Reissues second
sorted_rows = sorted(all_rows, key=lambda x: 0 if x[0] == "Original Press" else 1)

# Concatenate and wrap
icons_string = "".join([row[2] for row in sorted_rows])
wrapped_rows = [
    icons_string[i:i+WRAP] for i in range(0, len(icons_string), WRAP)
]

# Display centered icons (bigger)
icons_html = "<br>".join(wrapped_rows)
st.markdown(
    f"<div style='text-align:center; font-size:32px;'>{icons_html}</div>",
    unsafe_allow_html=True
)

# Legend below (smaller, gray, centered)
legend_html = " ".join(
    [f"{icons[t]} = {t} ({p:.1f}%)" for t, p, _ in sorted_rows]
)
st.markdown(
    f"<p style='text-align:center; color:gray; font-size:90%;'>{legend_html}</p>",
    unsafe_allow_html=True
)


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
# Random Album in Sidebar (thumbnail + metadata + prices in same markdown block)
# --------------------------

# Ensure we have album covers available (cached in session state)
if "all_covers" not in st.session_state:
    st.session_state.all_covers = df.dropna(subset=["cover_url"])

# Header + reload button in sidebar
col1, col2 = st.sidebar.columns([5, 1])
with col1:
    st.markdown("### 🎨 Random Album")
with col2:
    # use the column's button method (keeps it in the sidebar column)
    if col2.button("🔄", key="reload_album"):
        st.session_state.random_album = None  # only reset the random pick

# Pick or refresh a single random album (store a Series)
if "random_album" not in st.session_state or st.session_state.random_album is None:
    # sample(1).iloc[0] -> returns a pandas Series (single row)
    st.session_state.random_album = st.session_state.all_covers.sample(1).iloc[0]

album = st.session_state.random_album

# small helper to clean Discogs suffixes like " (5)"
def _clean_field(value):
    if not value or str(value).lower() == "nan":
        return "Unknown"
    if isinstance(value, (list, tuple)):
        return " / ".join(str(v).split(" (")[0] for v in value)
    return str(value).split(" (")[0]

cover_url = album.get("cover_url", "")
release_id = album.get("release_id", None)
artist = _clean_field(album.get("artists", album.get("artist", "Unknown")))
title = album.get("title", "Unknown")
label = _clean_field(album.get("labels", album.get("label", "Unknown")))
year = album.get("year", "Unknown")

link = f"https://www.discogs.com/release/{release_id}" if release_id else None

# --- Robust price fetching (single API call per random pick) ---
def fetch_price_stats_for_release(rid):
    """Fetch marketplace stats for a release and return numeric lowest/median/highest or None."""
    if not rid:
        return None
    url = f"https://api.discogs.com/marketplace/stats/{rid}?curr_abbr=USD"
    headers = {
        "User-Agent": "Niolu's Discogs Dashboard",
        "Authorization": f"Discogs token={st.secrets['DISCOGS_TOKEN']}"
    }
    try:
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    def _extract(v):
        """Accepts various shapes: number, string, or dict {'value':..., 'currency':...}"""
        if v is None:
            return None
        # direct numeric or string
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.replace(",", "").strip())
            except Exception:
                return None
        # expected dict shape
        if isinstance(v, dict):
            # common keys tried in order
            for k in ("value", "price", "amount"):
                if k in v and v[k] is not None:
                    try:
                        return float(v[k])
                    except Exception:
                        # string with commas?
                        try:
                            return float(str(v[k]).replace(",", "").strip())
                        except Exception:
                            continue
        return None

    # Try several possible key names (Discogs has had variations)
    lowest = _extract(data.get("lowest_price") or data.get("lowest") or data.get("low"))
    median = _extract(data.get("median_price") or data.get("median") or data.get("mid"))
    highest = _extract(data.get("highest_price") or data.get("highest") or data.get("high"))

    # If all None, return None to indicate no usable price info
    if lowest is None and median is None and highest is None:
        return None
    return {"lowest": lowest, "median": median, "highest": highest}

def _fmt_price(val):
    try:
        return f"${float(val):.2f}"
    except Exception:
        return "N/A"

prices = fetch_price_stats_for_release(release_id)

# --- Build a single markdown block with image + metadata + prices ---
price_block_html = ""
if prices:
    low_s = _fmt_price(prices.get("lowest"))
    med_s = _fmt_price(prices.get("median"))
    high_s = _fmt_price(prices.get("highest"))
    price_block_html = f"""
        <div style="margin-top:6px; font-size:90%; line-height:1.2;">
            💵 <b>Prices (USD)</b><br>
            Lowest: <span style="color:#27ae60;">{low_s}</span><br>
            Median: <span style="color:#2980b9;">{med_s}</span><br>
            Highest: <span style="color:#e74c3c;">{high_s}</span>
        </div>
    """

# show thumbnail + metadata + price block in one markdown block
st.sidebar.markdown(
    f"""
    <div style="text-align:center;">
        {"<a href='"+link+"' target='_blank'>" if link else ""}
            <img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:8px;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);"/>
        {"</a>" if link else ""}
        <p style="margin:6px 0 0 0;"><b>{artist}</b><br>{title}</p>
        <p style="margin:4px 0 0 0; color:gray; font-size:90%;">{label}, {year}</p>
        {price_block_html}
    </div>
    """,
    unsafe_allow_html=True
)

# --- videos (kept below the markdown block) ---
videos = fetch_release_videos(release_id) if release_id else []
if videos:
    st.sidebar.markdown("#### 🎥 Videos")
    for v in videos:
        uri = v.get("uri")
        if uri and ("youtube.com" in uri or "youtu.be" in uri):
            st.sidebar.video(uri)
        elif uri:
            st.sidebar.markdown(f"- [{v.get('title')}]({uri})")

# --- Styling: remove the box around the sidebar reload button only ---
st.sidebar.markdown(
    """
    <style>
    /* Target sidebar buttons (try to be specific so main buttons are unaffected) */
    aside .stButton button, section[aria-label="Sidebar"] .stButton button {
        background: none !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
        color: #e74c3c !important;
        font-size: 18px !important;
    }
    aside .stButton button:hover, section[aria-label="Sidebar"] .stButton button:hover {
        color: #c0392b !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------
# Data Preview
# --------------------------
with st.expander("🔍 Data Preview (click to expand)"):
    st.dataframe(df_filtered)











































































