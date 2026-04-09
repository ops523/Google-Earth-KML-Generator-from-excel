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

st.set_page_config(page_title="KML Geocoder (Precision Mode)", layout="wide")

st.title("📍 Excel to KML (High Accuracy + Clean Visuals)")

api_key = st.text_input("Enter LocationIQ API Key", type="password")
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])


# -------------------------------
# 🧹 CLEAN ADDRESS
# -------------------------------
def clean_address(row):
    address = str(row['Address'])

    address = re.sub(r'KHATA\s*#?\s*\d+', '', address, flags=re.IGNORECASE)
    address = re.sub(r'KHESRA\s*#?\s*\d+', '', address, flags=re.IGNORECASE)
    address = re.sub(r'THANA\s*#?\s*\d+', '', address, flags=re.IGNORECASE)
    address = re.sub(r'WARD\s*#?\s*\d+', '', address, flags=re.IGNORECASE)

    address = re.sub(r'#\d+', '', address)
    address = re.sub(r'\s+', ' ', address).strip()

    return f"{address}, {row['District']}, {row['State']}, India"


# -------------------------------
# 💾 CACHE
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
# 🧠 VALIDATION (STATE + CITY)
# -------------------------------
def is_valid_result(result, input_state, input_city):
    display = result.get("display_name", "").lower()

    state_ok = input_state.lower() in display

    # Loose city matching (handles spelling variations)
    city_ok = (
        input_city.lower() in display
        or input_city.lower().split()[0] in display
    )

    return state_ok and city_ok


# -------------------------------
# 🧭 GEOCODE
# -------------------------------
def geocode(row, api_key, cache):
    input_state = str(row['State']).strip()
    input_city = str(row['City']).strip()

    address_levels = [
        clean_address(row),
        f"{row['City']}, {row['District']}, {row['State']}, India",
        f"{row['District']}, {row['State']}, India"
    ]

    for level, address in enumerate(address_levels):

        if address in cache:
            d = cache[address]
            return d["lng"], d["lat"], f"CACHE_L{level+1}", address

        url = "https://us1.locationiq.com/v1/search.php"

        params = {
            "key": api_key,
            "q": address,
            "format": "json",
            "limit": 5,
            "countrycodes": "in"
        }

        try:
            r = requests.get(url, params=params, timeout=10)

            if r.status_code != 200:
                continue

            data = r.json()

            for result in data:
                if is_valid_result(result, input_state, input_city):
                    lat = float(result["lat"])
                    lng = float(result["lon"])

                    cache[address] = {"lat": lat, "lng": lng}
                    return lng, lat, f"LEVEL_{level+1}", address

        except:
            continue

    return None, None, "FAILED", address_levels[0]


# -------------------------------
# 🔵 SMOOTH CIRCLE
# -------------------------------
def create_circle(lat, lng, r):
    coords = []
    for i in range(72):  # smoother circle
        angle = math.radians(i * 5)
        dx = r * math.cos(angle)
        dy = r * math.sin(angle)

        new_lat = lat + (dy / 111)
        new_lng = lng + (dx / (111 * math.cos(math.radians(lat))))

        coords.append(f"{new_lng},{new_lat}")
    coords.append(coords[0])
    return " ".join(coords)


# -------------------------------
# 🎨 VISUAL STYLES
# -------------------------------
def add_styles(doc):
    styles = [
        ("circle1", "4dff0000"),  # light red
        ("circle2", "4d00ff00"),  # light green
        ("circle3", "4d0000ff")   # light blue
    ]

    for sid, color in styles:
        style = SubElement(doc, 'Style', id=sid)

        line = SubElement(style, 'LineStyle')
        SubElement(line, 'color').text = color
        SubElement(line, 'width').text = "1.5"

        poly = SubElement(style, 'PolyStyle')
        SubElement(poly, 'color').text = color


# -------------------------------
# 🗺️ GENERATE
# -------------------------------
def generate(df, api_key, batch_no, batch_size=50):

    cache = load_cache()

    start = (batch_no - 1) * batch_size
    end = start + batch_size
    df_batch = df.iloc[start:end]

    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = SubElement(kml, 'Document')

    add_styles(doc)

    progress = st.progress(0)

    results = []
    debug = []

    for i, row in df_batch.iterrows():

        lng, lat, status, addr = geocode(row, api_key, cache)

        debug.append({
            "Address": addr,
            "Lat": lat,
            "Lng": lng,
            "Status": status
        })

        if lat:
            city = str(row['City'])

            pm = SubElement(doc, 'Placemark')
            SubElement(pm, 'name').text = city

            pt = SubElement(pm, 'Point')
            SubElement(pt, 'coordinates').text = f"{lng},{lat}"

            for r, sid in [(1, "circle1"), (2, "circle2"), (3, "circle3")]:
                poly = SubElement(doc, 'Placemark')
                SubElement(poly, 'name').text = f"{city} | {r}km"
                SubElement(poly, 'styleUrl').text = f"#{sid}"

                polygon = SubElement(poly, 'Polygon')
                outer = SubElement(polygon, 'outerBoundaryIs')
                ring = SubElement(outer, 'LinearRing')

                SubElement(ring, 'coordinates').text = create_circle(lat, lng, r)

            results.append("✅")
        else:
            results.append("❌")

        progress.progress((len(results)) / len(df_batch))
        time.sleep(0.2)

    save_cache(cache)

    buffer = BytesIO()
    ElementTree(kml).write(buffer, encoding='utf-8', xml_declaration=True)

    df_batch["Status"] = results

    return buffer.getvalue(), df_batch, pd.DataFrame(debug)


# -------------------------------
# 🚀 RUN
# -------------------------------
if uploaded_file:
    df = pd.read_excel(uploaded_file)

    batch_no = st.number_input("Batch Number", min_value=1, value=1)

    if st.button("Generate KML"):

        kml, result, debug = generate(df, api_key, batch_no)

        st.download_button("Download KML", kml, f"batch_{batch_no}.kml")

        st.subheader("Results")
        st.dataframe(result)

        st.subheader("Debug")
        st.dataframe(debug)
