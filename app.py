import streamlit as st
import pandas as pd
import requests
import time
import math
from xml.etree.ElementTree import Element, SubElement, ElementTree
from io import BytesIO

st.set_page_config(page_title="KML Geocoder", layout="wide")

st.title("📍 Excel to KML with Radius (Production Version)")
st.write("Upload Excel → Clean → Geocode → Generate KML with coverage")

# 🔑 API Key
api_key = st.text_input("Enter Google Maps API Key", type="password")

# 📂 Upload
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# -------------------------------
# 🧹 Clean Address
# -------------------------------
def clean_address(row):
    base = str(row['Address']).replace("_", " ").replace("  ", " ").strip()

    city = str(row['City']).strip()
    state = str(row['State']).strip()
    pincode = str(row['Pincode']).strip()

    return f"{base}, {city}, {state}, {pincode}, India"


# -------------------------------
# 🧭 Geocode with retry
# -------------------------------
def geocode_address(address, api_key, retries=2):
    url = "https://maps.googleapis.com/maps/api/geocode/json"

    params = {
        "address": address,
        "key": api_key,
        "region": "in"
    }

    for attempt in range(retries + 1):
        try:
            response = requests.get(url, params=params)
            data = response.json()

            if data["status"] == "OK":
                loc = data["results"][0]["geometry"]["location"]
                return loc["lng"], loc["lat"], "OK"

            elif data["status"] in ["OVER_QUERY_LIMIT", "UNKNOWN_ERROR"]:
                time.sleep(1)  # retry delay
            else:
                return None, None, data["status"]

        except Exception as e:
            return None, None, "ERROR"

    return None, None, "FAILED"


# -------------------------------
# 🔵 Circle generator
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
# 🎨 Style creator
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
    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, 'Document')

    # Styles
    add_style(document, "circle1", "7dff0000")  # Red
    add_style(document, "circle2", "7d00ff00")  # Green
    add_style(document, "circle3", "7d0000ff")  # Blue

    progress = st.progress(0)
    status_text = st.empty()

    results = []
    debug_data = []

    for i, row in df.iterrows():
        address = clean_address(row)
        city = str(row['City'])

        status_text.text(f"Processing {i+1}/{len(df)}")

        lng, lat, status = geocode_address(address, api_key)

        debug_data.append({
            "Address Used": address,
            "Latitude": lat,
            "Longitude": lng,
            "Status": status
        })

        if lat is not None and lng is not None:
            # 📍 Main point
            placemark = SubElement(document, 'Placemark')
            SubElement(placemark, 'name').text = city
            SubElement(placemark, 'description').text = address

            point = SubElement(placemark, 'Point')
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
        time.sleep(0.05)

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
    if not api_key:
        st.error("Enter API key")
    elif not uploaded_file:
        st.error("Upload file")
    else:
        df = pd.read_excel(uploaded_file)

        required_cols = ["City", "State", "District", "Pincode", "Address"]
        if not all(col in df.columns for col in required_cols):
            st.error("Missing required columns!")
        else:
            st.info("Processing started...")

            kml_data, result_df, debug_df = generate_kml(df, api_key)

            st.success("KML generated!")

            st.download_button(
                "Download KML",
                kml_data,
                "locations_with_radius.kml"
            )

            st.subheader("✅ Summary")
            st.dataframe(result_df)

            st.subheader("🔍 Debug Data (Important)")
            st.dataframe(debug_df)
