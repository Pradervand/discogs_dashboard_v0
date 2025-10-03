# visualize_collection.py
import streamlit as st
import pandas as pd
import plotly.express as px
import random
from collection_dump import fetch_all_releases
import requests
import re
from streamlit_plotly_events import plotly_events


USER_TOKEN = st.secrets["DISCOGS_TOKEN"]
USERNAME = st.secrets["DISCOGS_USERNAME"]

USER_AGENT = "Niolu's Discogs test"   
BASE_URL = "https://api.discogs.com"

headers = {
    "User-Agent": USER_AGENT,
    "Authorization": f"Discogs token={USER_TOKEN}"
}

st.set_page_config(page_title="Discogs Collection Dashboard", layout="wide")
st.title("📀 Niolu's Vinyls Collection Dashboard")

# --------------------------
# Cached fetch
# --------------------------

import os

CACHE_FILE = "collection_cache.parquet"

@st.cache_data
def load_collection(username):
    if os.path.exists(CACHE_FILE):
        return pd.read_parquet(CACHE_FILE)
    else:
        df = fetch_all_releases(username)
        df.to_parquet(CACHE_FILE)
        return df

st.sidebar.subheader("🔄 Collection Control")
if st.sidebar.button("Update Collection from API"):
    with st.spinner("Fetching latest collection from Discogs..."):
        df = fetch_all_releases(USERNAME)
        df.to_parquet(CACHE_FILE)
        st.cache_data.clear()
        st.success("✅ Collection updated and cached!")

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
df_filtered = df

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
    total_spent = pd.to_numeric(df_filtered["PricePaid"], errors="coerce").sum()
    st.metric("💰 Total Spent (CHF)", f"{total_spent:,.2f}")


with col3:
    years = pd.to_numeric(df_filtered["year"], errors="coerce")
    years = years[years > 0]
    if not years.empty:
        st.metric("📅 Year Range", f"{int(years.min())} - {int(years.max())}")
    else:
        st.metric("📅 Year Range", "N/A")

with col4:
    if "labels" in df_filtered.columns and not df_filtered["labels"].dropna().empty:
        all_labels = (
            df_filtered["labels"]
            .dropna()
            .str.split(", ")
            .explode()
            .str.replace(r"\s*\(\d+\)$", "", regex=True)
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

## --------------------------
# Top TrueStyles
# --------------------------

st.subheader("🎼 Top TrueStyles")

def clean_truestyles(row):
    """Split TrueStyles field into a list, handling multiple line breaks and commas."""
    if pd.isna(row):
        return None
    # Split into lines, then split each line by commas
    parts = str(row).splitlines()
    styles = []
    for p in parts:
        styles.extend([s.strip() for s in p.split(",") if s.strip()])
    return styles if styles else None

df_styles = (
    df_filtered["TrueStyles"]
    .dropna()
    .apply(clean_truestyles)
    .dropna()
    .explode()   # expands multiple styles per record
    .value_counts()
    .reset_index()
)
df_styles.columns = ["Style", "Count"]

# ✅ Keep only styles with at least 2 records
df_styles = df_styles[df_styles["Count"] >= 2]

if df_styles.empty:
    st.warning("No valid TrueStyles (min 2 records) found in your collection.")
else:
    df_styles = df_styles.sort_values("Count", ascending=True)
    max_style = df_styles.loc[df_styles["Count"].idxmax(), "Style"]
    df_styles["Category"] = df_styles["Style"].apply(lambda s: "Max" if s == max_style else "Other")

    import plotly.express as px
    fig_styles = px.bar(
        df_styles,
        x="Count",
        y="Style",
        orientation="h",
        color="Category",
        title="Top TrueStyles (min 2 records)",
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig_styles.update_layout(
    showlegend=False,
    height=19 * len(df_styles)   # 30px per bar row
    )
    st.plotly_chart(fig_styles, use_container_width=True)



# --- TrueStyle Evolution ---
st.subheader("🎨 Cumulative Purchases over time by TrueStyle")

# Make sure 'added' is datetime
df["added"] = pd.to_datetime(df["added"], errors="coerce")

# Collect all TrueStyles with line-break aware splitting
all_styles = []
for s in df["TrueStyles"].dropna():
    parts = str(s).splitlines()
    for p in parts:
        all_styles.extend([x.strip() for x in p.split(",") if x.strip()])

# Count occurrences
style_counts = pd.Series(all_styles).value_counts()

# Keep only styles with at least 5 items
filtered_styles = sorted(style_counts[style_counts >= 5].index.tolist())

# TrueStyle selector
selected_style = st.selectbox("Select a TrueStyle", filtered_styles)

if selected_style:
    # Filter rows that contain the selected style
    mask = df["TrueStyles"].fillna("").str.contains(selected_style, case=False, na=False)
    df_style = df[mask].copy()

    if not df_style.empty:
        # Group purchases by month
        df_style["month"] = df_style["added"].dt.to_period("M").dt.to_timestamp()
        style_counts = (
            df_style.groupby("month").size().reset_index(name="Purchases")
        )
        # Convert to cumulative
        style_counts["Cumulative"] = style_counts["Purchases"].cumsum()

        fig = px.line(
            style_counts,
            x="month",
            y="Cumulative",
            markers=True,
            title=f"Cumulative Purchases Over Time — {selected_style}"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No purchases found for this TrueStyle.")



# --------------------------
# Pressing Types
# --------------------------
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

ICON_SCALE = 5
WRAP = 10

all_rows = []
for press_type, count in pressing_counts.items():
    if total > 0 and count > 0:
        percent = (count / total) * 100
        num_icons = max(1, int(round(percent / ICON_SCALE)))
        icon_block = "".join([icons[press_type]] * num_icons)
        all_rows.append((press_type, percent, icon_block))

sorted_rows = sorted(all_rows, key=lambda x: 0 if x[0] == "Original Press" else 1)

icons_string = "".join([row[2] for row in sorted_rows])
wrapped_rows = [icons_string[i:i+WRAP] for i in range(0, len(icons_string), WRAP)]

icons_html = "<br>".join(wrapped_rows)
st.markdown(f"<div style='text-align:center; font-size:32px;'>{icons_html}</div>", unsafe_allow_html=True)

legend_html = " ".join([f"{icons[t]} = {t} ({p:.1f}%)" for t, p, _ in sorted_rows])
st.markdown(f"<p style='text-align:center; color:gray; font-size:90%;'>{legend_html}</p>", unsafe_allow_html=True)

# --------------------------
# Spending & Sellers Analysis
# --------------------------
st.subheader("💸 Spending & Sellers Insights")

# Ensure numeric PricePaid
df_filtered["PricePaid"] = pd.to_numeric(df_filtered["PricePaid"], errors="coerce")

# Monthly spending trend
if not df_filtered["added"].isna().all():
    monthly_spending = (
        df_filtered.dropna(subset=["added", "PricePaid"])
        .set_index("added")
        .resample("M")["PricePaid"]
        .sum()
    )
    avg_monthly = monthly_spending.mean()

    st.metric("📊 Monthly Avg Spending", f"{avg_monthly:.2f} CHF")

    fig_spending = px.line(
        monthly_spending,
        x=monthly_spending.index,
        y=monthly_spending.values,
        title="Monthly Spending (CHF)",
        labels={"x": "Month", "y": "Total Spent (CHF)"}
    )
    st.plotly_chart(fig_spending, use_container_width=True)

# Favourite Seller
if "Seller" in df_filtered.columns:
    seller_counts = df_filtered["Seller"].value_counts()
    fav_seller = seller_counts.idxmax() if not seller_counts.empty else None
    fav_count = seller_counts.max() if not seller_counts.empty else 0
    st.metric("🏆 Favourite Seller", f"{fav_seller} ({fav_count} records)")

# Seller analysis: cheapest & most expensive (avg price, >3 records)
df_seller_stats = (
    df_filtered.dropna(subset=["Seller", "PricePaid"])
    .groupby("Seller")
    .agg(
        records=("PricePaid", "count"),
        avg_price=("PricePaid", "mean")
    )
    .reset_index()
)

df_seller_stats = df_seller_stats[df_seller_stats["records"] > 3]

if not df_seller_stats.empty:
    cheapest = df_seller_stats.loc[df_seller_stats["avg_price"].idxmin()]
    most_exp = df_seller_stats.loc[df_seller_stats["avg_price"].idxmax()]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("🟢 Cheapest Seller", f"{cheapest['Seller']} ({cheapest['avg_price']:.2f} CHF avg)")
    with col2:
        st.metric("🔴 Most Expensive Seller", f"{most_exp['Seller']} ({most_exp['avg_price']:.2f} CHF avg)")

    # Add color category: red for the most expensive seller, blue for the rest
    df_seller_stats["Category"] = df_seller_stats["Seller"].apply(
        lambda s: "Max" if s == most_exp["Seller"] else "Other"
    )

    fig_sellers = px.bar(
        df_seller_stats.sort_values("avg_price"),
        x="avg_price",
        y="Seller",
        orientation="h",
        color="Category",
        title="Average Price per Seller (min. 3 records)",
        labels={"avg_price": "Avg Price (CHF)", "Seller": "Seller"},
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig_sellers.update_layout(showlegend=False)
    st.plotly_chart(fig_sellers, use_container_width=True)

#####################
### Price Buckets ###
#####################
#####################

df_prices = df_filtered.dropna(subset=["PricePaid"])
bins = [0, 10, 25, 50, 100]
labels = ["0-10", "10-25", "25-50", "50-100"]

df_prices["price_bucket"] = pd.cut(
    df_prices["PricePaid"], 
    bins=bins, 
    labels=labels, 
    include_lowest=True, 
    ordered=True
)

# preserve order by reindexing explicitly
bucket_counts = (
    df_prices["price_bucket"]
    .value_counts(sort=False)  # don't sort by count
    .reindex(labels)           # ensure categorical order
    .reset_index()
)
bucket_counts.columns = ["Bucket", "Count"]

if not bucket_counts.empty:
    max_bucket = bucket_counts.loc[bucket_counts["Count"].idxmax(), "Bucket"]
    bucket_counts["Category"] = bucket_counts["Bucket"].apply(
        lambda b: "Max" if b == max_bucket else "Other"
    )

    fig = px.bar(
        bucket_counts,
        x="Bucket",
        y="Count",
        color="Category",
        title="Price Cohorts (CHF)",
        color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
    )
    fig.update_layout(showlegend=False, xaxis=dict(categoryorder="array", categoryarray=labels))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No price data available to build cohorts.")



# --------------------------
# Bands by Country (Recap with Flags + Toggle Table)
# --------------------------

# Full ISO3 -> ISO2 mapping (complete world list)
ISO3_TO_ISO2 = { 
    "AFG": "AF", "ALA": "AX", "ALB": "AL", "DZA": "DZ", "ASM": "AS", "AND": "AD",
    "AGO": "AO", "AIA": "AI", "ATA": "AQ", "ATG": "AG", "ARG": "AR", "ARM": "AM",
    "ABW": "AW", "AUS": "AU", "AUT": "AT", "AZE": "AZ", "BHS": "BS", "BHR": "BH",
    "BGD": "BD", "BRB": "BB", "BLR": "BY", "BEL": "BE", "BLZ": "BZ", "BEN": "BJ",
    "BMU": "BM", "BTN": "BT", "BOL": "BO", "BES": "BQ", "BIH": "BA", "BWA": "BW",
    "BVT": "BV", "BRA": "BR", "IOT": "IO", "BRN": "BN", "BGR": "BG", "BFA": "BF",
    "BDI": "BI", "CPV": "CV", "KHM": "KH", "CMR": "CM", "CAN": "CA", "CYM": "KY",
    "CAF": "CF", "TCD": "TD", "CHL": "CL", "CHN": "CN", "CXR": "CX", "CCK": "CC",
    "COL": "CO", "COM": "KM", "COG": "CG", "COD": "CD", "COK": "CK", "CRI": "CR",
    "CIV": "CI", "HRV": "HR", "CUB": "CU", "CUW": "CW", "CYP": "CY", "CZE": "CZ",
    "DNK": "DK", "DJI": "DJ", "DMA": "DM", "DOM": "DO", "ECU": "EC", "EGY": "EG",
    "SLV": "SV", "GNQ": "GQ", "ERI": "ER", "EST": "EE", "SWZ": "SZ", "ETH": "ET",
    "FLK": "FK", "FRO": "FO", "FJI": "FJ", "FIN": "FI", "FRA": "FR", "GUF": "GF",
    "PYF": "PF", "ATF": "TF", "GAB": "GA", "GMB": "GM", "GEO": "GE", "DEU": "DE",
    "GHA": "GH", "GIB": "GI", "GRC": "GR", "GRL": "GL", "GRD": "GD", "GLP": "GP",
    "GUM": "GU", "GTM": "GT", "GGY": "GG", "GIN": "GN", "GNB": "GW", "GUY": "GY",
    "HTI": "HT", "HMD": "HM", "HND": "HN", "HKG": "HK", "HUN": "HU", "ISL": "IS",
    "IND": "IN", "IDN": "ID", "IRN": "IR", "IRQ": "IQ", "IRL": "IE", "IMN": "IM",
    "ISR": "IL", "ITA": "IT", "JAM": "JM", "JPN": "JP", "JEY": "JE", "JOR": "JO",
    "KAZ": "KZ", "KEN": "KE", "KIR": "KI", "PRK": "KP", "KOR": "KR", "KWT": "KW",
    "KGZ": "KG", "LAO": "LA", "LVA": "LV", "LBN": "LB", "LSO": "LS", "LBR": "LR",
    "LBY": "LY", "LIE": "LI", "LTU": "LT", "LUX": "LU", "MAC": "MO", "MDG": "MG",
    "MWI": "MW", "MYS": "MY", "MDV": "MV", "MLI": "ML", "MLT": "MT", "MHL": "MH",
    "MTQ": "MQ", "MRT": "MR", "MUS": "MU", "MYT": "YT", "MEX": "MX", "FSM": "FM",
    "MDA": "MD", "MCO": "MC", "MNG": "MN", "MNE": "ME", "MSR": "MS", "MAR": "MA",
    "MOZ": "MZ", "MMR": "MM", "NAM": "NA", "NRU": "NR", "NPL": "NP", "NLD": "NL",
    "NCL": "NC", "NZL": "NZ", "NIC": "NI", "NER": "NE", "NGA": "NG", "NIU": "NU",
    "NFK": "NF", "MKD": "MK", "MNP": "MP", "NOR": "NO", "OMN": "OM", "PAK": "PK",
    "PLW": "PW", "PSE": "PS", "PAN": "PA", "PNG": "PG", "PRY": "PY", "PER": "PE",
    "PHL": "PH", "PCN": "PN", "POL": "PL", "PRT": "PT", "PRI": "PR", "QAT": "QA",
    "REU": "RE", "ROU": "RO", "RUS": "RU", "RWA": "RW", "BLM": "BL", "SHN": "SH",
    "KNA": "KN", "LCA": "LC", "MAF": "MF", "SPM": "PM", "VCT": "VC", "WSM": "WS",
    "SMR": "SM", "STP": "ST", "SAU": "SA", "SEN": "SN", "SRB": "RS", "SYC": "SC",
    "SLE": "SL", "SGP": "SG", "SXM": "SX", "SVK": "SK", "SVN": "SI", "SLB": "SB",
    "SOM": "SO", "ZAF": "ZA", "SGS": "GS", "SSD": "SS", "ESP": "ES", "LKA": "LK",
    "SDN": "SD", "SUR": "SR", "SJM": "SJ", "SWE": "SE", "CHE": "CH", "SYR": "SY",
    "TWN": "TW", "TJK": "TJ", "TZA": "TZ", "THA": "TH", "TLS": "TL", "TGO": "TG",
    "TKL": "TK", "TON": "TO", "TTO": "TT", "TUN": "TN", "TUR": "TR", "TKM": "TM",
    "TCA": "TC", "TUV": "TV", "UGA": "UG", "UKR": "UA", "ARE": "AE", "GBR": "GB",
    "USA": "US", "UMI": "UM", "URY": "UY", "UZB": "UZ", "VUT": "VU", "VEN": "VE",
    "VNM": "VN", "VGB": "VG", "VIR": "VI", "WLF": "WF", "ESH": "EH", "YEM": "YE",
    "ZMB": "ZM", "ZWE": "ZW"
}

def iso3_to_iso2(iso3):
    return ISO3_TO_ISO2.get(iso3.upper())

st.subheader("🌍 Bands by Country")

if "BandCountry" in df_filtered.columns and not df_filtered["BandCountry"].dropna().empty:
    # Count records per country
    country_counts = (
        df_filtered["BandCountry"]
        .dropna()
        .str.upper()
        .value_counts()
        .reset_index()
    )
    country_counts.columns = ["Country", "Count"]

    # --- Top 5 countries with flags ---
    st.markdown("### 🏳️ Top 5 Countries")

    top5 = country_counts.head(5)
    cols = st.columns(len(top5))

    for i, row in top5.iterrows():
        iso2 = iso3_to_iso2(row["Country"])
        count = row["Count"]

        with cols[list(top5.index).index(i)]:
            if iso2:
                flag_url = f"https://flagcdn.com/48x36/{iso2.lower()}.png"
                st.image(flag_url, width=48)
            st.metric(row["Country"], f"{count} bands")

    # --- Toggle full recap table ---
    if st.checkbox("Show full country table", value=False):
        st.markdown("### 📋 All Countries")
        st.dataframe(country_counts, use_container_width=True)

else:
    st.info("No country data available in BandCountry field.")




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

    # --- Extra stats ---
    avg_per_month = monthly_adds.mean()
    most_active_month = monthly_adds.idxmax()
    most_active_count = monthly_adds.max()

    # Growth last 12 months vs previous 12
    if len(monthly_adds) >= 24:
        last_12 = monthly_adds[-12:].sum()
        prev_12 = monthly_adds[-24:-12].sum()
        growth_pct = ((last_12 - prev_12) / prev_12 * 100) if prev_12 > 0 else None
    else:
        last_12, prev_12, growth_pct = None, None, None

    # --- Metrics Row ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📊 Avg per Month", f"{avg_per_month:.1f}")
    with col2:
        st.metric("🔥 Busiest Month", f"{most_active_count} records", str(most_active_month.strftime("%B %Y")))
    with col3:
        if growth_pct is not None:
            st.metric("📈 Last 12M Growth", f"{last_12} records", f"{growth_pct:+.1f}% vs prev 12M")
        else:
            st.metric("📈 Last 12M Growth", "N/A")

    # --- Plot ---
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


# --------------------------
# Random Album in Sidebar
# --------------------------
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

if "all_covers" not in st.session_state:
    st.session_state.all_covers = df.dropna(subset=["cover_url"])

col1, col2 = st.sidebar.columns([5, 1])
with col1:
    st.markdown("### 🎨 Random Album")
with col2:
    if st.button("🔄", key="reload_album"):
        st.session_state.random_album = None

if "random_album" not in st.session_state or st.session_state.random_album is None:
    st.session_state.random_album = st.session_state.all_covers.sample(1).iloc[0]

album = st.session_state.random_album

def clean_name(value):
    if not value or str(value).lower() == "nan":
        return "Unknown"
    if isinstance(value, (list, tuple)):
        return " / ".join(str(v).split(" (")[0] for v in value)
    return str(value).split(" (")[0]

cover_url = album.get("cover_url", "")
release_id = album.get("release_id", "")
artist = clean_name(album.get("artists", album.get("artist", "Unknown")))
title = album.get("title", "Unknown")
label = clean_name(album.get("labels", album.get("label", "Unknown")))
year = album.get("year", "Unknown")
link = f"https://www.discogs.com/release/{release_id}"

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

videos = fetch_release_videos(release_id)
if videos:
    st.sidebar.markdown("#### 🎥 Videos")
    for v in videos:
        uri = v.get("uri")
        if uri and ("youtube.com" in uri or "youtu.be" in uri):
            st.sidebar.video(uri)
        elif uri:
            st.sidebar.markdown(f"- [{v.get('title')}]({uri})")

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
with st.expander("🔍 Data Preview (click to expand)"):
    st.dataframe(df_filtered)































