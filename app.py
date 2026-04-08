import streamlit as st
import pandas as pd
import requests
import time
import math
import re
from xml.etree.ElementTree import Element, SubElement, ElementTree
from io import BytesIO

st.set_page_config(page_title="KML Geocoder (OSM Stable)", layout="wide")

st.title("📍 Excel to KML with Radius (Stable OSM Version)")
st.write("Reliable geocoding for Indian addresses using OpenStreetMap")

# 📂 Upload
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

    city = str(row['City']).strip()
    state = str(row['State']).strip()

    return f"{base}, {city}, {state}, India"


# -------------------------------
# 🧭 OSM Geocoding (FIXED)
# -------------------------------
def geocode_address_osm(row):
    url = "https://nominatim.openstreetmap.org/search"

    address_full = clean_address(row)
    address_city = f"{row['City']}, {row['State']}, India"

    headers = {
        "User-Agent": "Adwallz-KML-Tool/1.0 (ops@adwallz.com)"
    }

    for address, label in [(address_full, "FULL"), (address_city, "CITY_FALLBACK")]:
        params = {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "in"
        }

        for attempt in range(2):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=10
                )

                # Debug HTTP issues
                if response.status_code != 200:
                    return None, None, f"HTTP_{response.status_code}", address

                data = response.json()

                if isinstance(data, list) and len(data) > 0:
                    lat = float(data[0]["lat"])
                    lng = float(data[0]["lon"])
                    return lng, lat, label, address

                time.sleep(1)

            except Exception as e:
                return None, None, "ERROR", address

    return None, None, "FAILED", address_full


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
def generate_kml(df):
    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, 'Document')

    add_style(document, "circle1", "7dff0000")
    add_style(document, "circle2", "7d00ff00")
    add_style(document, "circle3", "7d0000ff")

    progress = st.progress(0)
    status_text = st.empty()

    results = []
    debug_data = []

    for i, row in df.iterrows():
        status_text.text(f"Processing {i+1}/{len(df)}")

        lng, lat, status, used_address = geocode_address_osm(row)

        debug_data.append({
            "Used Address": used_address,
            "Latitude": lat,
            "Longitude": lng,
            "Status": status
        })

        if lat is not None and lng is not None:
            city = str(row['City'])

            # 📍 Main Point
            pm = SubElement(document, 'Placemark')
            SubElement(pm, 'name').text = city
            SubElement(pm, 'description').text = used_address

            point = SubElement(pm, 'Point')
            SubElement(point, 'coordinates').text = f"{lng},{lat}"

            # 🔵 Circles
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

        progress.progress((i + 1) / len(df))
        time.sleep(1.2)  # 🚨 VERY IMPORTANT

    # Save KML
    tree = ElementTree(kml)
    buffer = BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)

    df["Status"] = results
    debug_df = pd.DataFrame(debug_data)

    return buffer.getvalue(), df, debug_df


# -------------------------------
# 🚀 RUN
# -------------------------------
if st.button("Generate KML"):
    if not uploaded_file:
        st.error("Please upload Excel file")
    else:
        df = pd.read_excel(uploaded_file)

        required_cols = ["City", "State", "District", "Pincode", "Address"]
        if not all(col in df.columns for col in required_cols):
            st.error("Missing required columns!")
        else:
            st.info("Processing (OSM safe mode — may take few minutes)...")

            kml_data, result_df, debug_df = generate_kml(df)

            st.success("KML generated successfully!")

            st.download_button(
                "Download KML",
                kml_data,
                "locations_with_radius.kml"
            )

            st.subheader("✅ Summary")
            st.dataframe(result_df)

            st.subheader("🔍 Debug Data (Check Status)")
            st.dataframe(debug_df)
