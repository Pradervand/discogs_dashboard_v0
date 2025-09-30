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
    """Remove 'Black Metal' if a more specific Black Metal sub-style is present."""
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
# Pressing Types
# ---------------------
st.subheader("📀 Pressing Types in Collection")

pressing_counts = {
    "Original Press": df_filtered["is_original"].sum(),
    "Repress/Reissue": df_filtered["is_reissue"].sum(),
    "Limited Edition": df_filtered["is_limited"].sum(),
}

pressing_df = pd.DataFrame(list(pressing_counts.items()), columns=["Type", "Count"])
max_type = pressing_df.loc[pressing_df["Count"].idxmax(), "Type"]
pressing_df["Category"] = pressing_df["Type"].apply(lambda t: "Max" if t == max_type else "Other")

fig_pressing = px.bar(
    pressing_df,
    x="Count",
    y="Type",
    orientation="h",
    color="Category",
    title="Proportion of Pressing Types",
    color_discrete_map={"Max": "#e74c3c", "Other": "#3498db"}
)
fig_pressing.update_layout(showlegend=False)
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
        color_discrete_map={
            "New records": "#3498db",  # blue
            "Cumulative": "#e74c3c"   # red
        }
    )
    st.plotly_chart(fig_growth, use_container_width=True)

    if missing_added > 0:
        st.info(f"⚠️ {missing_added} records had no parseable 'date_added' "
                f"and are excluded from the growth chart.")

# --------------------------
# Sidebar Album Covers
# --------------------------
st.sidebar.subheader("🎨 Random Album Covers")

if st.sidebar.button("🔄 Reload Covers"):
    st.session_state["cover_seed"] = random.randint(0, 100000)

seed = st.session_state.get("cover_seed", 42)

if len(df_filtered) >= 4:
    sample_df = df_filtered.sample(4, random_state=seed)
else:
    sample_df = df_filtered

cols = st.sidebar.columns(2)
for idx, (_, row) in enumerate(sample_df.iterrows()):
    cover_url = row.get("thumb_url") or row.get("cover_url")
    release_id = row.get("release_id")
    title = row.get("title")

    if cover_url and release_id:
        link = f"https://www.discogs.com/release/{release_id}"
        with cols[idx % 2]:
            st.markdown(
                f"""
                <a href="{link}" target="_blank">
                    <img src="{cover_url}" style="width:100%; border-radius:8px; margin-bottom:6px; box-shadow: 0 2px 6px rgba(0,0,0,0.2);"/>
                </a>
                <div style="text-align:center; font-size:11px; margin-bottom:12px;">{title}</div>
                """,
                unsafe_allow_html=True
            )

# --------------------------
# Data Preview
# --------------------------
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))
