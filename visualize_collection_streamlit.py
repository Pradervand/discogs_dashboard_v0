# visualize_collection.py
import streamlit as st
import pandas as pd
import plotly.express as px
from collection_dump import fetch_all_releases

USERNAME = st.secrets["DISCOGS_USERNAME"]

st.set_page_config(page_title="Discogs Collection Dashboard", layout="wide")
st.title("📀 My Discogs Collection Dashboard")

# --------------------------
# Fetch collection
# --------------------------
@st.cache_data(show_spinner=False)
def load_data():
    return fetch_all_releases(USERNAME)

with st.spinner("Fetching data from Discogs API..."):
    df = load_data()

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
df_year = df_filtered[df_filtered["year"] > 0]  # ignore year=0 and negatives

df_year = df_year["year"].value_counts().sort_index().reset_index()
df_year.columns = ["Year", "Count"]

if df_year.empty:
    st.warning("No valid release years found in your collection.")
else:
    max_year = df_year.loc[df_year["Count"].idxmax(), "Year"]
    colors = ["#e74c3c" if y == max_year else "#3498db" for y in df_year["Year"]]

    fig_year = px.bar(df_year, x="Year", y="Count", title="Records by Year")
    fig_year.update_traces(marker_color=colors)
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
    max_style = df_styles.loc[df_styles["Count"].idxmax(), "Style"]
    colors = ["#e74c3c" if s == max_style else "#3498db" for s in df_styles["Style"]]

    fig_styles = px.bar(
        df_styles,
        x="Count",
        y="Style",
        orientation="h",
        title="Top 15 Styles"
    )
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
df_pressings = pd.DataFrame({
    "Type": list(pressing_counts.keys()),
    "Proportion (%)": [round(v / total_pressings * 100, 1) if total_pressings > 0 else 0
                       for v in pressing_counts.values()]
}).sort_values("Proportion (%)", ascending=False)

if df_pressings.empty:
    st.warning("No pressing type data available.")
else:
    max_type = df_pressings.loc[df_pressings["Proportion (%)"].idxmax(), "Type"]
    colors = ["#e74c3c" if t == max_type else "#3498db" for t in df_pressings["Type"]]

    fig_pressing = px.bar(
        df_pressings,
        x="Proportion (%)",
        y="Type",
        orientation="h",
        title="Proportion of Pressing Types"
    )
    fig_pressing.update_traces(marker_color=colors)
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
        title=f"Discogs Collection Growth Over Time "
              f"(showing {len(df_time)} / {len(df_filtered)} records)"
    )
    fig_growth.update_traces(line=dict(color="#3498db"), selector=dict(name="New records"))
    fig_growth.update_traces(line=dict(color="#e74c3c"), selector=dict(name="Cumulative"))
    st.plotly_chart(fig_growth, use_container_width=True)

    if missing_added > 0:
        st.info(f"⚠️ {missing_added} records had no parseable 'date_added' "
                f"and are excluded from the growth chart.")

# --------------------------
# Random Album Covers
# --------------------------
st.subheader("🎨 Random Album Covers")

if st.button("🔄 Reload Covers", help="Show 12 random covers"):
    if "cover_random" in st.session_state:
        del st.session_state["cover_random"]

if "cover_random" not in st.session_state:
    st.session_state["cover_random"] = df_filtered.dropna(
        subset=["cover_image"]
    ).sample(n=min(12, len(df_filtered)), replace=False)

cols = st.columns(3)
for i, row in enumerate(st.session_state["cover_random"].itertuples()):
    cover_url = row.cover_image
    release_id = row.release_id
    link = f"https://www.discogs.com/release/{release_id}"
    with cols[i % 3]:
        st.markdown(
            (
                f'<a href="{link}" target="_blank">'
                f'<img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:8px; '
                'box-shadow: 0 2px 6px rgba(0,0,0,0.2);"/>'
                '</a>'
            ),
            unsafe_allow_html=True
        )

# --------------------------
# Data Preview
# --------------------------
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))
