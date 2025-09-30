# visualize_collection.py
import streamlit as st
import pandas as pd
import plotly.express as px
import random
from collection_dump import fetch_all_releases

USERNAME = st.secrets["DISCOGS_USERNAME"]

# --------------------------
# Page setup
# --------------------------
st.set_page_config(page_title="Discogs Collection Dashboard", layout="wide")
st.title("📀 My Discogs Collection Dashboard")

# --------------------------
# Cache API + data prep
# --------------------------
@st.cache_data
def load_collection(username):
    return fetch_all_releases(username)

@st.cache_data
def extract_covers(df):
    return df.dropna(subset=["cover_url"])

@st.cache_data
def parse_dates(df):
    df = df.copy()
    df["added"] = pd.to_datetime(
        df["added"], errors="coerce", utc=True, infer_datetime_format=True
    )
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    return df

# --------------------------
# Load data
# --------------------------
with st.spinner("Fetching data from Discogs API... (cached after first run)"):
    df = load_collection(USERNAME)

df = parse_dates(df)
covers_df = extract_covers(df)

# --------------------------
# Sidebar filters
# --------------------------
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
# Random Album Covers (Sidebar)
# --------------------------
col1, col2 = st.sidebar.columns([5, 1])
with col1:
    st.markdown("### 🎨 Random Album Covers")
with col2:
    if st.button("🔄", key="reload_covers"):
        st.session_state.random_albums = None

def pick_random_albums(df, n=12):
    if len(df) <= n:
        return df.index.tolist()
    return random.sample(list(df.index), n)

if "random_albums" not in st.session_state or st.session_state.random_albums is None:
    st.session_state.random_albums = pick_random_albums(covers_df)

cols = st.sidebar.columns(3)
for i, idx in enumerate(st.session_state.random_albums):
    row = covers_df.loc[idx]
    cover_url = row["cover_url"]
    release_id = row["release_id"]
    link = f"https://www.discogs.com/release/{release_id}"
    with cols[i % 3]:
        st.markdown(
            f(
                '<a href="{link}" target="_blank">'
                f'<img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:8px;'
                'box-shadow: 0 2px 6px rgba(0,0,0,0.2);"/>'
                '</a>'
            ),
            unsafe_allow_html=True
        )
# Style reload button
st.markdown(
    """
    <style>
    div.stButton > button:first-child {
        background: none;
        border: none;
        color: #e74c3c;
        font-size: 18px;
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
# Records by Year
# --------------------------
st.subheader("📅 Records by Year")
df_year = df_filtered[df_filtered["year"] > 0]
df_year = df_year["year"].value_counts().sort_index().reset_index()
df_year.columns = ["Year", "Count"]

if df_year.empty:
    st.warning("No valid release years found in your collection.")
else:
    max_year = df_year.loc[df_year["Count"].idxmax(), "Year"]
    colors = ["#e74c3c" if y == max_year else "#3498db" for y in df_year["Year"]]
    fig_year = px.bar(df_year, x="Year", y="Count", title="Records by Year")
    fig_year.update_traces(marker_color=colors)
    fig_year.update_layout(height=500)
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
    fig_styles = px.bar(df_styles, x="Count", y="Style", orientation="h", title="Top 15 Styles")
    max_style = df_styles.loc[df_styles["Count"].idxmax(), "Style"]
    colors = ["#e74c3c" if s == max_style else "#3498db" for s in df_styles["Style"]]
    fig_styles.update_traces(marker_color=colors)
    fig_styles.update_layout(yaxis=dict(autorange="reversed"), height=600)
    st.plotly_chart(fig_styles, use_container_width=True)

# ---------------------
# Pressing Types
# ---------------------
st.subheader("📀 Pressing Types in Collection")

pressing_counts = {
    "Original Press": df_filtered["is_original"].sum(),
    "Repress/Reissue": df_filtered["is_reissue"].sum(),
    "Limited Edition": df_filtered["is_limited"].sum(),
}
total_pressings = sum(pressing_counts.values())
pressing_percent = {k: (v / total_pressings) * 100 for k, v in pressing_counts.items()}

df_pressing = pd.DataFrame({
    "Type": list(pressing_percent.keys()),
    "Proportion (%)": list(pressing_percent.values())
}).sort_values("Proportion (%)", ascending=False)

fig_pressing = px.bar(
    df_pressing,
    x="Proportion (%)",
    y="Type",
    orientation="h",
    text="Proportion (%)",
    title="Pressing Types (Proportion %)"
)
max_type = df_pressing.loc[df_pressing["Proportion (%)"].idxmax(), "Type"]
colors = ["#e74c3c" if t == max_type else "#3498db" for t in df_pressing["Type"]]
fig_pressing.update_traces(marker_color=colors, texttemplate="%{text:.1f}%")
fig_pressing.update_layout(yaxis=dict(autorange="reversed"), height=400)
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
        title=f"Discogs Collection Growth Over Time (showing {len(df_time)} / {len(df_filtered)} records)"
    )
    fig_growth.update_traces(line=dict(color="#e74c3c"), selector=dict(name="New records"))
    fig_growth.update_traces(line=dict(color="#3498db"), selector=dict(name="Cumulative"))
    fig_growth.update_layout(height=500)
    st.plotly_chart(fig_growth, use_container_width=True)

    if missing_added > 0:
        st.info(f"⚠️ {missing_added} records had no parseable 'date_added' and are excluded from the growth chart.")

# --------------------------
# Data Preview
# --------------------------
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))
