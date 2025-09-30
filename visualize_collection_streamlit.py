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
# Fetch collection
# --------------------------
with st.spinner("Fetching data from Discogs API..."):
    df = fetch_all_releases(USERNAME)

# Parse dates safely
df["added"] = pd.to_datetime(
    df["added"],
    errors="coerce",
    utc=True,
    infer_datetime_format=True
)

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
# --------------------------
# Fetch data ONCE and cache
# --------------------------
@st.cache_data(show_spinner="Fetching data from Discogs API...")
def load_collection(username):
    return fetch_all_releases(username)

df = load_collection(USERNAME)

# Pre-extract all albums with covers
if "all_covers" not in st.session_state:
    st.session_state.all_covers = df.dropna(subset=["cover_url"])

# --------------------------
# Album Art Preview in Sidebar (grid)
# --------------------------

col1, col2 = st.sidebar.columns([5, 1])
with col1:
    st.markdown("### 🎨 Random Album Covers")
with col2:
    if st.button("🔄", key="reload_covers"):
        st.session_state.random_albums = None  # trigger re-pick

def pick_random_albums(df, n=12):
    if len(df) <= n:
        return df.index.tolist()
    return random.sample(list(df.index), n)

# Pick from cached covers only
if "random_albums" not in st.session_state or st.session_state.random_albums is None:
    st.session_state.random_albums = pick_random_albums(st.session_state.all_covers)

# Display covers in 3-column grid
cols = st.sidebar.columns(3)
for i, idx in enumerate(st.session_state.random_albums):
    row = st.session_state.all_covers.loc[idx]
    cover_url = row["cover_url"]
    release_id = row["release_id"]
    title = row["title"]
    link = f"https://www.discogs.com/release/{release_id}"
    with cols[i % 3]:
        st.markdown(
            f"""
            <a href="{link}" target="_blank">
                <img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:8px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);"/>
            </a>
            """,
            unsafe_allow_html=True
        )

# Style reload button as icon
st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        background: none;
        border: none;
        color: #e74c3c;
        font-size: 20px;
        padding: 0;
        margin: 0;
    }
    div.stButton > button:first-child:hover {
        color: #c0392b;
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








