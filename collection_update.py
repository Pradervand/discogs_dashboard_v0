# collection_update.py
import os
import time
import pandas as pd
from collection_dump import safe_request, get_instance_fields, get_custom_fields_map, USERNAME, FOLDER_ID, BASE_URL

CACHE_FILE = "collection_cache.parquet"

def save_cache(df):
    try:
        df.to_parquet(CACHE_FILE, index=False)
    except Exception:
        df.to_csv(CACHE_FILE.replace(".parquet", ".csv"), index=False)

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            return pd.read_parquet(CACHE_FILE)
        except Exception:
            csvfile = CACHE_FILE.replace(".parquet", ".csv")
            if os.path.exists(csvfile):
                return pd.read_csv(csvfile)
    return pd.DataFrame()

def fetch_latest_releases(username, folder_id=0, per_page=5, page=1):
    url = f"{BASE_URL}/users/{username}/collection/folders/{folder_id}/releases"
    params = {"sort": "added", "sort_order": "desc", "per_page": per_page, "page": page}
    return safe_request(url, params=params)

def incremental_update(username=USERNAME, folder_id=FOLDER_ID, per_page=5, max_pages=50):
    df_cache = load_cache()
    if df_cache.empty or "instance_id" not in df_cache.columns:
        known_instances = set()
    else:
        known_instances = set(df_cache["instance_id"].dropna().astype(str))

    # field ids
    price_id, seller_id, bandcountry_id = 4, 5, 6
    try:
        field_map = get_custom_fields_map(username)
        price_id = field_map.get("PricePaid", price_id)
        seller_id = field_map.get("Seller", seller_id)
        bandcountry_id = field_map.get("BandCountry", bandcountry_id)
    except Exception:
        pass

    new_records = []
    page = 1
    while page <= max_pages:
        data = fetch_latest_releases(username, folder_id, per_page, page)
        releases = data.get("releases", [])
        if not releases:
            break

        for item in releases:
            inst_id = str(item.get("instance_id"))
            if inst_id in known_instances:
                if new_records:
                    df_new = pd.DataFrame(new_records)
                    df_cache = pd.concat([df_new, df_cache], ignore_index=True)
                    save_cache(df_cache)
                    return df_cache, new_records
                return df_cache, []

            bi = item.get("basic_information", {})
            release_id = bi.get("id")

            notes = get_instance_fields(username, folder_id, release_id, inst_id)
            field_dict = {n.get("field_id"): n.get("value") for n in notes if n.get("field_id")}

            formats = bi.get("formats", [])
            format_names = [f.get("name") for f in formats if f.get("name")]
            format_desc = []
            for f in formats:
                if isinstance(f, dict):
                    if "descriptions" in f and isinstance(f["descriptions"], list):
                        format_desc.extend(f["descriptions"])
                    if f.get("text"):
                        format_desc.append(f["text"])

            rec = {
                "release_id": release_id,
                "instance_id": inst_id,
                "title": bi.get("title"),
                "year": bi.get("year"),
                "artists": ", ".join([a.get("name") for a in bi.get("artists", [])]) if bi.get("artists") else None,
                "labels": ", ".join([l.get("name") for l in bi.get("labels", [])]) if bi.get("labels") else None,
                "cover_url": bi.get("cover_image"),
                "thumb_url": bi.get("thumb"),
                "formats": ", ".join(format_names) if format_names else None,
                "format_descriptions": ", ".join(format_desc) if format_desc else None,
                "genres": ", ".join(bi.get("genres", [])) if bi.get("genres") else None,
                "styles": ", ".join(bi.get("styles", [])) if bi.get("styles") else None,
                "rating": item.get("rating"),
                "added": item.get("date_added"),
                # Custom fields
                "PricePaid": field_dict.get(price_id),
                "Seller": field_dict.get(seller_id),
                "BandCountry": field_dict.get(bandcountry_id),
                # Optional booleans if defined in your notes
                "is_limited": field_dict.get("is_limited"),
                "is_reissue": field_dict.get("is_reissue"),
                "is_original": field_dict.get("is_original"),
            }
            new_records.append(rec)

        page += 1
        time.sleep(0.2)

    if new_records:
        df_new = pd.DataFrame(new_records)
        df_cache = pd.concat([df_new, df_cache], ignore_index=True)
        save_cache(df_cache)
        return df_cache, new_records

    return df_cache, []
