# -*- coding: utf-8 -*-
"""
Created on Tue Sep 30 09:51:19 2025

@author: antony.praderva
"""

import requests
import time
import pandas as pd


USER_TOKEN = "KntqUVHoEIzzkAKmHyqNqnygkKaedhdUjTQulQUy"
USERNAME = "Niolu"
USER_AGENT = "Niolu's Discogs test"   


BASE_URL = "https://api.discogs.com"

headers = {
    "User-Agent": USER_AGENT,
    "Authorization": f"Discogs token={USER_TOKEN}"
}

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
            rec = {
                "release_id": bi.get("id"),
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([artist.get("name") for artist in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([lbl.get("name") for lbl in bi.get("labels", [])]) if bi.get("labels") else None,
                "formats": ", ".join([fmt.get("name") for fmt in bi.get("formats", [])]) if bi.get("formats") else None,
                "styles": ", ".join(bi.get("styles", [])) if bi.get("styles") else None,
                "genres": ", ".join(bi.get("genres", [])) if bi.get("genres") else None,
                "added": item.get("date_added"),                
                "rating": item.get("rating")
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

