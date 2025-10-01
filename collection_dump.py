import requests
import time
import pandas as pd
import streamlit as st

USER_TOKEN = st.secrets["DISCOGS_TOKEN"]
USERNAME = st.secrets["DISCOGS_USERNAME"]
USER_AGENT = "Discogs Collection Script"
BASE_URL = "https://api.discogs.com"

headers = {
    "User-Agent": USER_AGENT,
    "Authorization": f"Discogs token={USER_TOKEN}"
}

# ---------- API helpers ----------

def get_collection_folder_releases(username, folder_id=0, page=1, per_page=100):
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases"
    params = {"page": page, "per_page": per_page}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

def get_custom_fields(username):
    url = f"{BASE_URL}/users/{username}/collection/fields"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return {f["name"]: f["id"] for f in resp.json().get("fields", [])}

@st.cache_data(show_spinner=False)
def get_instance_fields(username, folder_id, release_id, instance_id):
    """Fetch and cache custom field values for one instance."""
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("fields", [])

# ---------- Main fetcher with progress bar ----------

def fetch_all_releases(username, folder_id=0):
    all_records = []
    page = 1
    per_page = 100

    field_map = get_custom_fields(username)

    # First count total records
    first_page = get_collection_folder_releases(username, folder_id, page=1, per_page=1)
    total_records = first_page["pagination"]["items"]

    progress = st.progress(0, text=f"Fetching releases (0 / {total_records})")
    fetched = 0

    while True:
        data = get_collection_folder_releases(username, folder_id, page=page, per_page=per_page)
        releases = data.get("releases", [])
        if not releases:
            break

        for item in releases:
            bi = item.get("basic_information", {})
            instance_id = item.get("instance_id")
            release_id = bi.get("id")

            # Cached call per release
            field_values = get_instance_fields(username, folder_id, release_id, instance_id)
            field_dict = {f["field_id"]: f.get("value") for f in field_values}

            rec = {
                "release_id": release_id,
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([a["name"] for a in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([l["name"] for l in bi.get("labels", [])]) if bi.get("labels") else None,
                "added": item.get("date_added"),
                "PricePaid": field_dict.get(field_map.get("PricePaid")),
                "Seller": field_dict.get(field_map.get("Seller")),
                "BandCountry": field_dict.get(field_map.get("BandCountry")),
            }
            all_records.append(rec)

            # Update progress
            fetched += 1
            progress.progress(fetched / total_records, text=f"Fetching releases ({fetched} / {total_records})")

            time.sleep(1)  # rate limit protection

        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 0):
            break
        page += 1

    progress.empty()  # clear the progress bar
    return pd.DataFrame(all_records)
