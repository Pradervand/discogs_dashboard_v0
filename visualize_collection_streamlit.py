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
df_year = df_filtered[df_filtered["year"] > 0]  # ignore year=0 and negatives

df_year = df_year["year"].value_counts().sort_index().reset_index()
df_year.columns = ["Year", "Count"]

if df_year.empty:
    st.warning("No valid release years found in your collection.")
else:
    # Find max year
    max_count = df_year["Count"].max()
    df_year["Highlight"] = df_year["Count"].apply(
        lambda x: "Most Productive Year" if x == max_count else "Other"
    )

    fig_year = px.bar(
        df_year,
        x="Year",
        y="Count",
        color="Highlight",
        title="Records by Year",
        color_discrete_map={
            "Most Productive Year": "#e74c3c",  # bright red
            "Other": "#95a5a6"  # neutral gray
        }
    )

    # Hide legend (since only 2 categories)
    fig_year.update_layout(showlegend=False)

    st.plotly_chart(fig_year, use_container_width=True)


# --------------------------
# Top Styles
# --------------------------
# --------------------------
# Top Styles
# --------------------------
st.subheader("🎼 Top Styles")

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
    max_count = df_styles["Count"].max()
    df_styles["Highlight"] = df_styles["Count"].apply(
        lambda x: "Max" if x == max_count else "Other"
    )

    fig_styles = px.bar(
        df_styles,
        x="Count",
        y="Style",
        orientation="h",
        title="Top 15 Styles",
        color="Highlight",
        color_discrete_map={
            "Max": "#e74c3c",   # red
            "Other": "#95a5a6"  # gray
        }
    )
    fig_styles.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"))
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

df_pressing = pd.DataFrame(
    list(pressing_counts.items()),
    columns=["Pressing Type", "Count"]
)

max_count = df_pressing["Count"].max()
df_pressing["Highlight"] = df_pressing["Count"].apply(
    lambda x: "Max" if x == max_count else "Other"
)

fig_pressing = px.bar(
    df_pressing,
    x="Count",
    y="Pressing Type",
    orientation="h",
    text="Count",
    title="Pressing Types in Your Collection",
    color="Highlight",
    color_discrete_map={
        "Max": "#e74c3c",
        "Other": "#95a5a6"
    }
)

fig_pressing.update_traces(textposition="outside")
fig_pressing.update_layout(showlegend=False, yaxis=dict(categoryorder="total ascending"))
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
            "Cumulative": "#e74c3c"    # red
        }
    )
    st.plotly_chart(fig_growth, use_container_width=True)

    if missing_added > 0:
        st.info(f"⚠️ {missing_added} records had no parseable 'date_added' "
                f"and are excluded from the growth chart.")

# --------------------------
# Data Preview
# --------------------------
st.subheader("🔍 Data Preview")
st.dataframe(df_filtered.head(50))


