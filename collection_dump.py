# -*- coding: utf-8 -*-
"""
Created on Tue Sep 30 09:51:19 2025

@author: antony.praderva
"""

import requests
import time
import pandas as pd
import streamlit as st

# Load secrets
USER_TOKEN = st.secrets["DISCOGS_TOKEN"]
USERNAME = st.secrets["DISCOGS_USERNAME"]

USER_AGENT = "Niolu's Discogs test"   
BASE_URL = "https://api.discogs.com"

headers = {
    "User-Agent": USER_AGENT,
    "Authorization": f"Discogs token={USER_TOKEN}"
}
def get_custom_fields(username):
    """Fetch the list of custom fields for the user."""
    url = f"{BASE_URL}/users/{username}/collection/fields"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return {f["id"]: f["name"] for f in resp.json().get("fields", [])}


def get_instance_fields(username, folder_id, release_id, instance_id):
    """Fetch field values for a specific instance in the collection."""
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json().get("fields", [])


def fetch_all_releases(username, folder_id=0):
    all_records = []
    page = 1
    per_page = 100 

    # First get field definitions
    field_map = get_custom_fields(username)

    while True:
        data = get_collection_folder_releases(username, folder_id, page=page, per_page=per_page)
        releases = data.get("releases", [])
        if not releases:
            break

        for item in releases:
            bi = item.get("basic_information", {})
            instance_id = item.get("instance_id")
            release_id = bi.get("id")

            # Extra call to get field values
            field_values = get_instance_fields(username, folder_id, release_id, instance_id)
            field_dict = {f["field_id"]: f.get("value") for f in field_values}

            rec = {
                "release_id": release_id,
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([artist.get("name") for artist in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([lbl.get("name") for lbl in bi.get("labels", [])]) if bi.get("labels") else None,
                "formats": ", ".join([fmt.get("name") for fmt in bi.get("formats", [])]) if bi.get("formats") else None,
                "genres": ", ".join(bi.get("genres", [])) if bi.get("genres") else None,
                "styles": ", ".join(bi.get("styles", [])) if bi.get("styles") else None,
                "added": item.get("date_added"),
                "rating": item.get("rating"),
                # Custom fields by name
                "PricePaid": field_dict.get(4),
                "Seller": field_dict.get(5),
                "BandCountry": field_dict.get(6),
            }

            all_records.append(rec)

        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 0):
            break
        page += 1
        time.sleep(1)

    return pd.DataFrame(all_records)


if __name__ == "__main__":
    df = fetch_all_releases(USERNAME, folder_id=0)  
    print(df.head())
    print(f"Fetched {len(df)} records")







