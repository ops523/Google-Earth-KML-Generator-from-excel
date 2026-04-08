import streamlit as st
import pandas as pd
import requests
import time
from xml.etree.ElementTree import Element, SubElement, ElementTree
from io import BytesIO

st.set_page_config(page_title="KML Geocoder", layout="wide")

st.title("📍 Excel to KML (Google Geocoding)")
st.write("Upload your Excel file → Generate map-ready KML")

# 🔑 API Key Input
api_key = st.text_input("Enter Google Maps API Key", type="password")

# 📂 File Upload
uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# 🧭 Geocode Function
def geocode_address(address, api_key):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {
        "address": address,
        "key": api_key
    }

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

# 🗺️ Generate KML
def generate_kml(df, api_key):
    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, 'Document')

    progress = st.progress(0)
    status_text = st.empty()

    results = []

    for i, row in df.iterrows():
        address = str(row.get('Address', ''))
        city = str(row.get('City', f'Location {i+1}'))

        status_text.text(f"Processing {i+1}/{len(df)}")

        lng, lat = geocode_address(address, api_key)

        if lat and lng:
            placemark = SubElement(document, 'Placemark')

            name = SubElement(placemark, 'name')
            name.text = city

            desc = SubElement(placemark, 'description')
            desc.text = address

            point = SubElement(placemark, 'Point')
            coords = SubElement(point, 'coordinates')
            coords.text = f"{lng},{lat}"

            results.append("✅")
        else:
            results.append("❌")

        progress.progress((i + 1) / len(df))
        time.sleep(0.05)

    # Convert KML to bytes
    tree = ElementTree(kml)
    buffer = BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)

    df["Status"] = results

    return buffer.getvalue(), df

# 🚀 Run Button
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

        # 📥 Download KML
        st.download_button(
            label="Download KML File",
            data=kml_data,
            file_name="locations.kml",
            mime="application/vnd.google-earth.kml+xml"
        )

        # 📊 Show results
        st.subheader("Processing Summary")
        st.dataframe(result_df)
