import math

# 🧭 Create Circle (as polygon)
def create_circle(lat, lng, radius_km, num_points=36):
    points = []
    for i in range(num_points):
        angle = math.radians(float(i) / num_points * 360)

        dx = radius_km * math.cos(angle)
        dy = radius_km * math.sin(angle)

        new_lat = lat + (dy / 111)  # approx conversion
        new_lng = lng + (dx / (111 * math.cos(math.radians(lat))))

        points.append(f"{new_lng},{new_lat}")

    points.append(points[0])  # close polygon
    return " ".join(points)


# 🗺️ Generate KML with circles
def generate_kml(df, api_key):
    kml = Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = SubElement(kml, 'Document')

    # 🎨 Styles for circles
    def add_style(doc, style_id, color):
        style = SubElement(doc, 'Style', id=style_id)
        line = SubElement(style, 'LineStyle')
        SubElement(line, 'color').text = color
        SubElement(line, 'width').text = "2"

        poly = SubElement(style, 'PolyStyle')
        SubElement(poly, 'color').text = color

    add_style(document, "circle1", "7dff0000")  # red (1km)
    add_style(document, "circle2", "7d00ff00")  # green (2km)
    add_style(document, "circle3", "7d0000ff")  # blue (3km)

    progress = st.progress(0)
    status_text = st.empty()

    results = []

    for i, row in df.iterrows():
        address = str(row.get('Address', ''))
        city = str(row.get('City', f'Location {i+1}'))

        status_text.text(f"Processing {i+1}/{len(df)}")

        lng, lat = geocode_address(address, api_key)

        if lat and lng:
            # 📍 Main Point
            placemark = SubElement(document, 'Placemark')

            name = SubElement(placemark, 'name')
            name.text = city

            desc = SubElement(placemark, 'description')
            desc.text = address

            point = SubElement(placemark, 'Point')
            coords = SubElement(point, 'coordinates')
            coords.text = f"{lng},{lat}"

            # 🔵 Add Circles (1km, 2km, 3km)
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

    # 💾 Save
    tree = ElementTree(kml)
    buffer = BytesIO()
    tree.write(buffer, encoding='utf-8', xml_declaration=True)

    df["Status"] = results

    return buffer.getvalue(), df
