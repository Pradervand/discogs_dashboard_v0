import requests
import time
import pandas as pd
import streamlit as st
from requests_oauthlib import OAuth1

# -----------------------
# Config
# -----------------------
BASE_URL = "https://api.discogs.com"
USER_AGENT = "Discogs Collection Dashboard"

# Fill in with your OAuth1 credentials
CONSUMER_KEY = "NNzITfKaEgvPJUmTvUQJ"
CONSUMER_SECRET = "CQOUAamarejgrqLUmeqGwxXPfvTwDsyW"
OAUTH_TOKEN = "SkQsCJblkmEYVsMcOjnijXpjRJnIcBsIFvyATgLf"
OAUTH_TOKEN_SECRET = "BRAkgpOzowAiaEoWQDofRPxLxZUtowdZBUfKqctB"
USERNAME = "Niolu"
FOLDER_ID = 0

# -----------------------
# Auth setup
# -----------------------
auth = OAuth1(
    CONSUMER_KEY,
    client_secret=CONSUMER_SECRET,
    resource_owner_key=OAUTH_TOKEN,
    resource_owner_secret=OAUTH_TOKEN_SECRET
)

headers = {"User-Agent": USER_AGENT}

# -----------------------
# Safe request wrapper
# -----------------------
def safe_request(url, params=None, progress=None):
    """Perform a GET request with automatic handling of Discogs rate limits (429)."""
    while True:
        resp = requests.get(url, headers=headers, params=params, auth=auth)

        if resp.status_code == 429:  # Too Many Requests
            reset_after = int(resp.headers.get("Retry-After", 60))
            msg = f"⚠️ Rate limit hit. Pausing for {reset_after} seconds..."
            print(msg)
            if progress:
                progress.text(msg)
            time.sleep(reset_after)
            continue  # retry after sleeping

        resp.raise_for_status()
        return resp.json()

# -----------------------
# API helpers
# -----------------------
def get_collection_folder_releases(username, folder_id=0, page=1, per_page=100, progress=None):
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases"
    params = {"page": page, "per_page": per_page}
    return safe_request(url, params=params, progress=progress)


def get_custom_fields_map(username, progress=None):
    url = f"{BASE_URL}/users/{username}/collection/fields"
    try:
        fields = safe_request(url, progress=progress).get("fields", [])
        return {f.get("name"): f.get("id") for f in fields if "name" in f and "id" in f}
    except Exception as e:
        print(f"Warning: could not fetch custom fields: {e}")
        return {}


def get_instance_fields(username, folder_id, release_id, instance_id, progress=None):
    if not instance_id:
        return []
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases/{release_id}/instances/{instance_id}"
    try:
        data = safe_request(url, progress=progress)
        # ✅ Discogs stores custom field values in "notes", not "fields"
        return data.get("notes", []) or []
    except Exception as e:
        print(f"Warning: failed to fetch instance fields for {release_id}/{instance_id}: {e}")
        return []

# -----------------------
# Main fetcher
# -----------------------
def fetch_all_releases(username, folder_id=0):
    """
    Fetch collection and return DataFrame with full metadata
    + PricePaid, Seller, BandCountry fields.
    Includes progress bar and automatic rate-limit handling.
    """
    all_records = []
    page = 1
    per_page = 100

    # progress bar setup
    first_page = get_collection_folder_releases(username, folder_id, page=1, per_page=1)
    total_records = first_page["pagination"]["items"]
    fetched = 0
    progress = st.progress(0, text=f"Fetching releases (0 / {total_records})")

    # get custom field map
    field_name_to_id = get_custom_fields_map(username, progress=progress)
    price_id = field_name_to_id.get("PricePaid") or 4
    seller_id = field_name_to_id.get("Seller") or 5
    bandcountry_id = field_name_to_id.get("BandCountry") or 6

    instance_cache = {}

    while True:
        data = get_collection_folder_releases(username, folder_id, page=page, per_page=per_page, progress=progress)
        releases = data.get("releases", [])
        if not releases:
            break

        for item in releases:
            bi = item.get("basic_information", {})
            formats = bi.get("formats", [])
            fmt_desc = []
            for f in formats:
                if "descriptions" in f:
                    fmt_desc.extend(f["descriptions"])

            fmt_desc_lower = [d.lower() for d in fmt_desc]
            is_reissue = any("repress" in d or "reissue" in d for d in fmt_desc_lower)
            is_limited = any("limited edition" in d for d in fmt_desc_lower)
            is_original = not is_reissue

            instance_id = item.get("instance_id")
            release_id = bi.get("id")

            price_paid_val = None
            seller_val = None
            bandcountry_val = None

            if instance_id:
                cache_key = f"{release_id}_{instance_id}"
                if cache_key in instance_cache:
                    field_dict = instance_cache[cache_key]
                else:
                    field_values = get_instance_fields(username, folder_id, release_id, instance_id, progress=progress)
                    field_dict = {
                        fv.get("field_id"): fv.get("value")
                        for fv in field_values if fv.get("field_id") is not None
                    }
                    instance_cache[cache_key] = field_dict
                    time.sleep(1)  # normal pacing to avoid burst

                price_paid_val = field_dict.get(price_id)
                seller_val = field_dict.get(seller_id)
                bandcountry_val = field_dict.get(bandcountry_id)

            rec = {
                "release_id": bi.get("id"),
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([a.get("name") for a in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([l.get("name") for l in bi.get("labels", [])]) if bi.get("labels") else None,
                "formats": ", ".join([f.get("name") for f in formats]) if formats else None,
                "format_descriptions": ", ".join(fmt_desc) if fmt_desc else None,
                "genres": ", ".join(bi.get("genres", [])) if bi.get("genres") else None,
                "styles": ", ".join(bi.get("styles", [])) if bi.get("styles") else None,
                "added": item.get("date_added"),
                "rating": item.get("rating"),
                "cover_url": bi.get("cover_image"),
                "thumb_url": bi.get("thumb"),
                "is_limited": is_limited,
                "is_reissue": is_reissue,
                "is_original": is_original,
                "PricePaid": price_paid_val,
                "Seller": seller_val,
                "BandCountry": bandcountry_val,
            }

            all_records.append(rec)

            # update progress bar
            fetched += 1
            progress.progress(fetched / total_records, text=f"Fetching releases ({fetched} / {total_records})")

        pagination = data.get("pagination", {})
        if page >= pagination.get("pages", 0):
            break
        page += 1
        time.sleep(0.5)  # gentle pause between pages

    progress.empty()
    return pd.DataFrame(all_records)
