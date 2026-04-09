import streamlit as st
import pandas as pd
import requests
import time
import math
import re
import json
import os
from xml.etree.ElementTree import Element, SubElement, ElementTree
from io import BytesIO

st.set_page_config(page_title="KML Geocoder (LocationIQ)", layout="wide")

st.title("📍 Excel to KML with Radius (Stable Version)")
st.write("Powered by LocationIQ (No blocking, high success rate)")

# 🔑 API KEY INPUT
api_key = st.text_input("Enter LocationIQ API Key", type="password")

# 📂 Upload file
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# -------------------------------
# 🧹 Clean Address
# -------------------------------
def clean_address(row):
    base = str(row['Address'])
    base = re.sub(r'#\d+', '', base)
    base = base.replace("_", " ")
    base = re.sub(r'[^a-zA-Z0-9, ]', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()

    return f"{base}, {row['City']}, {row['State']}, India"


# -------------------------------
# 💾 Cache
# -------------------------------
def load_cache():
    if os.path.exists("geocode_cache.json"):
        with open("geocode_cache.json", "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open("geocode_cache.json", "w") as f:
        json.dump(cache, f)


# -------------------------------
# 🧭 LocationIQ Geocoding
# -------------------------------
def geocode_address_locationiq(row, api_key, cache):
    address = clean_address(row)

    # Cache check
    if address in cache:
        data = cache[address]
        return data["lng"], data["lat"], "CACHE", address

    url = "https://us1.locationiq.com/v1/search.php"

    params = {
        "key": api_key,
        "q": address,
        "format": "json",
        "limit": 1,
        "countrycodes": "in"
    }

    try:
        response = requests.get(url, params=params, timeout=10)

        if response.status_code != 200:
            return None, None, f"HTTP_{response.status_code}", address

        data = response.json()

        if isinstance(data, list) and len(data) > 0:
            lat = float(data[0]["lat"])
            lng = float(data[0]["lon"])

            cache[address] = {"lat": lat, "lng": lng}

            return lng, lat, "OK", address

    except:
        return None, None, "ERROR", address

    return None, None, "FAILED", address


# -------------------------------
# 🔵 Circle Generator
# -------------------------------
def create_circle(lat, lng, radius_km, points=36):
    coords = []

    for i in range(points):
        angle = math.radians(i * 360 / points)

        dx = radius_km * math.cos(angle)
        dy = radius_km * math.sin(angle)

        new_lat = lat + (dy / 111)
        new_lng = lng + (dx / (111 * math.cos(math.radians(lat))))

        coords.append(f"{new_lng},{new_lat}")

    coords.append(coords[0])
    return " ".join(coords)


# -------------------------------
# 🎨 Styles
# -------------------------------
def add_style(doc, style_id, color):
    style = SubElement(doc, 'Style', id=style_id)

    line = SubElement(style, 'LineStyle')
    SubElement(line, 'color').text = color
    SubElement(line, 'width').text = "2"

    poly = SubElement(style, 'PolyStyle')
    SubElement(poly, 'color').text = color


# -------------------------------
# 🗺️ Generate KML
# -------------------------------
def generate_kml(df, api_key):
    cache = load_cache()

    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, 'Document')

    add_style(document, "circle1", "7dff0000")
    add_style(document, "circle2", "7d00ff00")
    add_style(document, "circle3", "7d0000ff")

    progress = st.progress(0)
    status_text = st.empty()

    results = []
    debug_data = []

    BATCH_SIZE = 50
    df_batch = df.head(BATCH_SIZE)

    for i, row in df_batch.iterrows():
        status_text.text(f"Processing {i+1}/{len(df_batch)}")

        lng, lat, status, used_address = geocode_address_locationiq(row, api_key, cache)

        debug_data.append({
            "Used Address": used_address,
            "Latitude": lat,
            "Longitude": lng,
            "Status": status
        })

        if lat is not None and lng is not None:
            city = str(row['City'])

            pm = SubElement(document, 'Placemark')
            SubElement(pm, 'name').text = city
            SubElement(pm, 'description').text = used_address

            point = SubElement(pm, 'Point')
            SubElement(point, 'coordinates').text = f"{lng},{lat}"

            for r, sid in [(1, "circle1"), (2, "circle2"), (3, "circle3")]:
                poly_pm = SubElement(document, 'Placemark')
                SubElement(poly_pm, 'name').text = f"{city} - {r} km"
                SubElement(poly_pm, 'styleUrl').text = f"#{sid}"

                polygon = SubElement(poly_pm, 'Polygon')
                outer = SubElement(polygon, 'outerBoundaryIs')
                linear = SubElement(outer, 'LinearRing')

                SubElement(linear, 'coordinates').text = create_circle(lat, lng, r)

            results.append("✅")
        else:
            results.append("❌")

        progress.progress((i + 1) / len(df_batch))

        time.sleep(0.2)  # fast + safe for LocationIQ

    save_cache(cache)

    tree = ElementTree(kml)
    buffer = BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)

    df_batch["Status"] = results
    debug_df = pd.DataFrame(debug_data)

    return buffer.getvalue(), df_batch, debug_df


# -------------------------------
# 🚀 RUN
# -------------------------------
if st.button("Generate KML"):
    if not api_key:
        st.error("Enter LocationIQ API Key")
    elif not uploaded_file:
        st.error("Upload Excel file")
    else:
        df = pd.read_excel(uploaded_file)

        required_cols = ["City", "State", "District", "Pincode", "Address"]
        if not all(col in df.columns for col in required_cols):
            st.error("Missing required columns!")
        else:
            st.info("Processing (fast & stable)...")

            kml_data, result_df, debug_df = generate_kml(df, api_key)

            st.success("KML generated successfully!")

            st.download_button(
                "Download KML",
                kml_data,
                "locations.kml"
            )

            st.subheader("✅ Summary")
            st.dataframe(result_df)

            st.subheader("🔍 Debug Data")
            st.dataframe(debug_df)
