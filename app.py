import streamlit as st
import pandas as pd
import requests
import time
import math
from xml.etree.ElementTree import Element, SubElement, ElementTree
from io import BytesIO

st.set_page_config(page_title="KML Geocoder", layout="wide")

st.title("📍 Excel to KML with Radius (Google Maps)")
st.write("Upload your Excel file → Generate KML with 1km, 2km, 3km coverage")

# 🔑 API Key input
api_key = st.text_input("Enter Google Maps API Key", type="password")

# 📂 Upload file
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# -------------------------------
# 🧭 Geocode function
# -------------------------------
def geocode_address(address, api_key):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": api_key}

    try:
        response = requests.get(url, params=params)
        data = response.json()

        if data["status"] == "OK":
            location = data["results"][0]["geometry"]["location"]
            return location["lng"], location["lat"]
        else:
            return None, None
    except:
        return None, None


# -------------------------------
# 🔵 Create circle polygon
# -------------------------------
def create_circle(lat, lng, radius_km, num_points=36):
    points = []
    for i in range(num_points):
        angle = math.radians(float(i) / num_points * 360)

        dx = radius_km * math.cos(angle)
        dy = radius_km * math.sin(angle)

        new_lat = lat + (dy / 111)
        new_lng = lng + (dx / (111 * math.cos(math.radians(lat))))

        points.append(f"{new_lng},{new_lat}")

    points.append(points[0])  # close loop
    return " ".join(points)


# -------------------------------
# 🎨 Add style
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

    # Circle styles
    add_style(document, "circle1", "7dff0000")  # Red
    add_style(document, "circle2", "7d00ff00")  # Green
    add_style(document, "circle3", "7d0000ff")  # Blue

    progress = st.progress(0)
    status_text = st.empty()

    results = []

    for i, row in df.iterrows():
        address = str(row.get('Address', ''))
        city = str(row.get('City', f'Location {i+1}'))

        status_text.text(f"Processing {i+1}/{len(df)}")

        lng, lat = geocode_address(address, api_key)

        if lat and lng:
            # 📍 Main location
            placemark = SubElement(document, 'Placemark')

            name = SubElement(placemark, 'name')
            name.text = city

            desc = SubElement(placemark, 'description')
            desc.text = address

            point = SubElement(placemark, 'Point')
            coords = SubElement(point, 'coordinates')
            coords.text = f"{lng},{lat}"

            # 🔵 Add radius circles
            for radius, style_id in [(1, "circle1"), (2, "circle2"), (3, "circle3")]:
                circle_coords = create_circle(lat, lng, radius)

                poly_pm = SubElement(document, 'Placemark')
                SubElement(poly_pm, 'name').text = f"{city} - {radius} km"
                SubElement(poly_pm, 'styleUrl').text = f"#{style_id}"

                polygon = SubElement(poly_pm, 'Polygon')
                outer = SubElement(polygon, 'outerBoundaryIs')
                linear = SubElement(outer, 'LinearRing')
                SubElement(linear, 'coordinates').text = circle_coords

            results.append("✅")
        else:
            results.append("❌")

        progress.progress((i + 1) / len(df))
        time.sleep(0.05)

    # Convert to bytes
    tree = ElementTree(kml)
    buffer = BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)

    df["Status"] = results

    return buffer.getvalue(), df


# -------------------------------
# 🚀 Run button
# -------------------------------
if st.button("Generate KML"):
    if not api_key:
        st.error("Please enter API Key")
    elif not uploaded_file:
        st.error("Please upload Excel file")
    else:
        df = pd.read_excel(uploaded_file)

        st.info("Processing started...")

        kml_data, result_df = generate_kml(df, api_key)

        st.success("KML generated successfully!")

        # Download KML
        st.download_button(
            label="Download KML File",
            data=kml_data,
            file_name="locations_with_radius.kml",
            mime="application/vnd.google-earth.kml+xml"
        )

        # Show table
        st.subheader("Processing Summary")
        st.dataframe(result_df)
