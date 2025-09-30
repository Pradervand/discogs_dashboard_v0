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

def fetch_release_duration(release_id):
    """Fetch tracklist and compute total runtime for a release."""
    url = f"{DISCOGS_API_BASE}/releases/{release_id}"
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        tracklist = data.get("tracklist", [])
        total_seconds = sum(parse_duration(t.get("duration")) for t in tracklist)
        return total_seconds
    except Exception:
        return 0
def get_collection_folder_releases(username, folder_id=0, page=1, per_page=100):
    """
    Fetch one page of releases in a given collection folder.
    """
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases"
    params = {
        "page": page,
        "per_page": per_page
    }
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    data = resp.json()
    return data

def fetch_all_releases(username, folder_id=0):
    """
    Loop through all pages to fetch all releases.
    """
    all_records = []
    page = 1
    per_page = 100 

    while True:
        data = get_collection_folder_releases(username, folder_id, page=page, per_page=per_page)
        releases = data.get("releases", [])
        if not releases:
            break

        for item in releases:
            bi = item.get("basic_information", {})

            # --- Formats and pressing info ---
            formats = bi.get("formats", [])
            fmt_desc = []
            for f in formats:
                if "descriptions" in f:
                    fmt_desc.extend(f["descriptions"])

            # Normalize to lowercase for detection
            fmt_desc_lower = [d.lower() for d in fmt_desc]

            is_reissue = any("repress" in d or "reissue" in d for d in fmt_desc_lower)
            is_limited = any("limited edition" in d for d in fmt_desc_lower)
            is_original = not is_reissue  # If not tagged as repress/reissue → original press

            rec = {
                "release_id": bi.get("id"),
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([artist.get("name") for artist in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([lbl.get("name") for lbl in bi.get("labels", [])]) if bi.get("labels") else None,
                "formats": ", ".join([fmt.get("name") for fmt in formats]) if formats else None,
                "format_descriptions": ", ".join(fmt_desc) if fmt_desc else None,
                "genres": ", ".join(bi.get("genres", [])) if bi.get("genres") else None,
                "styles": ", ".join(bi.get("styles", [])) if bi.get("styles") else None,
                "added": item.get("date_added"),                
                "rating": item.get("rating"),
                "cover_url": bi.get("cover_image"),   
                "thumb_url": bi.get("thumb"),        
                "is_limited": is_limited,
                "is_reissue": is_reissue,
                "is_original": is_original
            }
            all_records.append(rec)
       
        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 0):
            break
        page += 1
        
        time.sleep(1)  # respect API rate limit
    
    return pd.DataFrame(all_records)

if __name__ == "__main__":
    df = fetch_all_releases(USERNAME, folder_id=0)  
    print(df.head())
    print(f"Fetched {len(df)} records")


