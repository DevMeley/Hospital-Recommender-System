# recommender.py

import pandas as pd
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import googlemaps
import os
import logging
import re
import polyline
from datetime import datetime
from jinja2 import Template
from math import radians, sin, cos, sqrt, atan2
from dotenv import load_dotenv

load_dotenv() 

# Setup logging
logging.basicConfig(filename='hospital_recommender.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default coordinates (Lagos center)
DEFAULT_COORDS = (6.5244, 3.3792)

# Maximum distance threshold for proximity (in km)
MAX_DISTANCE = 10.0

def get_valid_category(value, default):
    valid_options = {"low", "medium", "high"}
    value = value.strip().lower() if value else default.lower()
    if value in valid_options:
        return value.capitalize()
    logger.warning(f'Invalid input "{value}". Using default: {default}')
    return default.capitalize()

def map_preference_to_value(pref):
    pref_map = {"Low": 0.33, "Medium": 0.66, "High": 1.0}
    return pref_map.get(pref, 0.33)

def compute_service_match(user_service, hospital_services):
    if pd.isna(hospital_services) or pd.isna(user_service):
        logger.warning('Missing service data')
        return 0.0
    user_service = user_service.lower().strip()
    hospital_services = hospital_services.lower().strip()
    hospital_service_list = [s.strip() for s in hospital_services.split(',')]
    if user_service == 'surgery':
        if 'surgery' in hospital_service_list or 'surgical services' in hospital_service_list:
            if all(svc not in hospital_service_list for svc in ['dental surgery', 'oral surgery', 'cosmetic surgery']):
                logger.info(f'Exact match for "surgery" in {hospital_service_list}')
                return 1.0
            else:
                logger.info(f'Excluded mismatch for "surgery" in {hospital_service_list}')
                return 0.0
        elif any('surgery' in svc and 'dental' not in svc and 'oral' not in svc and 'cosmetic' not in svc for svc in hospital_service_list):
            logger.info(f'Partial match for "surgery" in {hospital_service_list}')
            return 0.95
        logger.info(f'No match for "surgery" in {hospital_service_list}')
        return 0.0
    if user_service in hospital_service_list:
        logger.info(f'Exact match for "{user_service}" in {hospital_service_list}')
        return 1.0
    elif any(user_service in svc for svc in hospital_service_list):
        logger.info(f'Strong partial match for "{user_service}" in {hospital_service_list}')
        return 0.95
    elif any(word in ' '.join(hospital_service_list) for word in user_service.split()):
        logger.info(f'Weak partial match for "{user_service}" in {hospital_service_list}')
        return 0.5
    logger.info(f'No match for "{user_service}" in {hospital_service_list}')
    return 0.0

def map_cost_rating(cost_rating):
    if pd.isna(cost_rating) or cost_rating == 'N/A':
        return 1.0
    cost_map = {"Low": 1.0, "Medium": 2.0, "High": 3.0, "Premium": 3.0}
    return cost_map.get(cost_rating.strip().capitalize(), 1.0)

def load_geocode_cache(cache_file="hospital_coordinates.csv"):
    if os.path.exists(cache_file):
        try:
            cache = pd.read_csv(cache_file, index_col="Address")
            return cache.to_dict()["Coordinates"]
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    return {}

def save_geocode_cache(cache, cache_file="hospital_coordinates.csv"):
    try:
        cache_df = pd.DataFrame.from_dict(cache, orient="index", columns=["Coordinates"])
        cache_df.index.name = "Address"
        cache_df.to_csv(cache_file)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def geocode_address(address, cache):
    if address in cache:
        coords_str = cache[address]
        if coords_str == "None":
            return DEFAULT_COORDS
        try:
            lat, lon = map(float, coords_str.strip("()").split(","))
            return (lat, lon)
        except:
            logger.warning(f"Invalid cached coordinates for '{address}'. Re-geocoding.")
    
    # Simulate geocoding with a placeholder (replace with actual OSM Nominatim API if needed)
    try:
        # Placeholder: Assume address parsing or use a service like Nominatim
        # For now, use DEFAULT_COORDS as fallback
        cache[address] = f"({DEFAULT_COORDS[0]},{DEFAULT_COORDS[1]})"
        return DEFAULT_COORDS
    except Exception as e:
        logger.error(f"Geocoding error for '{address}': {e}")
        cache[address] = "None"
        return DEFAULT_COORDS

def get_driving_route(user_coords, hospital_coords, hospital_name):
    # Placeholder: OSM routing (e.g., OSRM) requires a separate API call
    # For now, return None as driving data isn't available without integration
    return None, None, None

def haversine_distance(coord1, coord2):
    """Calculate straight-line distance between two coordinates in kilometers."""
    lat1, lon1 = radians(coord1[0]), radians(coord1[1])
    lat2, lon2 = radians(coord2[0]), radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    R = 6371  # Earth radius in kilometers
    return R * c

def extract_city(address):
    cities = (
        r'Ikorodu|Ikoyi|Ikeja|Victoria Island|Surulere|Badagry|Lagos Island|Agege|'
        r'Alimosho|Apapa|Epe|Eti-Osa|Ibeju-Lekki|Ifako-Ijaiye|Kosofe|Lagos Mainland|'
        r'Mushin|Ojo|Oshodi-Isolo|Shomolu|Ajeromi-Ifelodun|Amuwo-Odofin|'
        r'Lekki|Ajah|Yaba|Gbagada|Maryland|Ilupeju|Ketu|Magodo|Ojota|Egbeda|'
        r'Idimu|Ipaja|Bariga|Festac Town|Amuwo|Isolo|Okota|Ikotun|Ogudu|'
        r'Alagbado|Ojodu|Iju|Akoka|Somolu|Agidingbi|Ogba|Isheri|Agbara|Ijanikin'
    )
    match = re.search(f'({cities})', address, re.IGNORECASE)
    if match:
        return match.group(1).lower()
    last_phrase = address.split(',')[-1].strip().lower()
    if last_phrase in ['lagos', 'nigeria', 'state', 'lga', 'unknown', '']:
        return 'unknown'
    return last_phrase

def generate_map_html(recommendations, user_coords, user_service, location):
    """Generate HTML with an interactive OpenStreetMap for recommended hospitals using Leaflet."""
    if recommendations.empty:
        return None
    
    # Prepare hospital data for JavaScript
    hospitals = []
    for idx, row in recommendations.iterrows():
        coords = row["Coordinates"]
        hospitals.append({
            "name": row["Name"],
            "address": row["Full Address"],
            "services": row["Services"],
            "cost_level": row["Cost Level"],
            "quality_score": row["Quality Score"],
            "recommendation_score": round(row["Recommendation_Score"], 3),
            "lat": coords[0],
            "lng": coords[1],
            "route_distance": row["Route_Distance"] if pd.notna(row["Route_Distance"]) else "N/A",
            "route_duration": row["Route_Duration"] if pd.notna(row["Route_Duration"]) else "N/A"
        })
    
    # Center map on user location or Lagos default
    center_lat, center_lng = user_coords if user_coords != DEFAULT_COORDS else DEFAULT_COORDS
    
    # HTML template with Leaflet and OpenStreetMap
    template = Template("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Hospital Recommendations Map</title>
        <style>
            #map { height: 500px; width: 100%; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .address-link { color: blue; cursor: pointer; text-decoration: underline; }
        </style>
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    </head>
    <body>
        <h2>Recommended Hospitals for {{ service }} in {{ location }}</h2>
        <div id="map"></div>
        <table>
            <tr>
                <th>Name</th>
                <th>Address</th>
                <th>Services</th>
                <th>Cost Level</th>
                <th>Quality Score</th>
                <th>Recommendation Score</th>
                <th>Distance</th>
                <th>Duration</th>
            </tr>
            {% for hospital in hospitals %}
            <tr>
                <td>{{ hospital.name }}</td>
                <td><span class="address-link" onclick="panToHospital({{ hospital.lat }}, {{ hospital.lng }}, '{{ hospital.name | replace("'", "\\'") }}')">{{ hospital.address }}</span></td>
                <td>{{ hospital.services }}</td>
                <td>{{ hospital.cost_level }}</td>
                <td>{{ hospital.quality_score }}</td>
                <td>{{ hospital.recommendation_score }}</td>
                <td>{{ hospital.route_distance }}</td>
                <td>{{ hospital.route_duration }}</td>
            </tr>
            {% endfor %}
        </table>
        <script>
            let map;
            let markers = [];
            function initMap() {
                map = L.map('map').setView([{ center_lat }, { center_lng }], 12);
                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    maxZoom: 19,
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }).addTo(map);
                {% for hospital in hospitals %}
                const marker = L.marker([{{ hospital.lat }}, {{ hospital.lng }}]).addTo(map)
                    .bindPopup(`
                        <div>
                            <h3>{{ hospital.name | replace("'", "\\'") }}</h3>
                            <p><strong>Address:</strong> {{ hospital.address | replace("'", "\\'") }}</p>
                            <p><strong>Services:</strong> {{ hospital.services | replace("'", "\\'") }}</p>
                            <p><strong>Cost Level:</strong> {{ hospital.cost_level }}</p>
                            <p><strong>Quality Score:</strong> {{ hospital.quality_score }}</p>
                            <p><strong>Recommendation Score:</strong> {{ hospital.recommendation_score }}</p>
                        </div>
                    `);
                markers.push({marker: marker, name: '{{ hospital.name | replace("'", "\\'") }}'});
                {% endfor %}
            }
            function panToHospital(lat, lng, name) {
                map.setView([lat, lng], 15);
                markers.forEach(m => {
                    if (m.name === name) {
                        m.marker.openPopup();
                    } else {
                        m.marker.closePopup();
                    }
                });
            }
            window.onload = initMap;
        </script>
    </body>
    </html>
    """)
    
    # Render HTML
    html_content = template.render(
        hospitals=hospitals,
        service=user_service,
        location=location.title(),
        center_lat=center_lat,
        center_lng=center_lng
    )
    
    # Save HTML file
    try:
        map_file = "static/map_output.html"
        os.makedirs(os.path.dirname(map_file), exist_ok=True)
        with open(map_file, "w") as f:
            f.write(html_content)
        logger.info(f"Interactive map saved to {map_file}")
        return map_file
    except Exception as e:
        logger.error(f"Error saving map HTML: {e}")
        return None

def setup_fuzzy_system():
    cost = ctrl.Antecedent(np.arange(1, 3.1, 0.1), 'cost')
    quality = ctrl.Antecedent(np.arange(2, 5.1, 0.1), 'quality')
    service_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'service_match')
    proximity_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'proximity_match')
    recommendation = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'recommendation')

    # Membership functions
    cost['low'] = fuzz.trimf(cost.universe, [1, 1, 1.5])
    cost['medium'] = fuzz.trimf(cost.universe, [1.2, 1.5, 2])
    cost['high'] = fuzz.trimf(cost.universe, [1.5, 2, 2.5])
    cost['premium'] = fuzz.trimf(cost.universe, [2, 3, 3])

    quality['low'] = fuzz.trimf(quality.universe, [2, 2, 3])
    quality['medium'] = fuzz.trimf(quality.universe, [2.5, 3, 4])
    quality['high'] = fuzz.trimf(quality.universe, [3.5, 4.5, 5])

    service_match['low'] = fuzz.trimf(service_match.universe, [0, 0, 0.3])
    service_match['medium'] = fuzz.trimf(service_match.universe, [0.2, 0.5, 0.7])
    service_match['high'] = fuzz.trimf(service_match.universe, [0.6, 1, 1])

    proximity_match['far'] = fuzz.trimf(proximity_match.universe, [0, 0, 0.3])
    proximity_match['medium'] = fuzz.trimf(proximity_match.universe, [0.2, 0.5, 0.7])
    proximity_match['close'] = fuzz.trimf(proximity_match.universe, [0.6, 1, 1])

    recommendation['low'] = fuzz.trimf(recommendation.universe, [0, 0, 0.4])
    recommendation['medium'] = fuzz.trimf(recommendation.universe, [0.3, 0.5, 0.6])
    recommendation['high'] = fuzz.trimf(recommendation.universe, [0.7, 0.85, 1])

    # Fuzzy rules (36 rules adjusted for proximity)
    rules = [
        # Low cost preference
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['low'] & (service_match['low'] | proximity_match['far']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['low'] & proximity_match['far'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['medium']),

        # Medium cost preference
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & (service_match['low'] | proximity_match['far']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['low'] & proximity_match['far'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['medium']),

        # High cost preference
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['medium'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['high'] & (service_match['low'] | proximity_match['far']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['high'] & service_match['low'] & proximity_match['far'] & quality['low'], recommendation['low']),

        # Premium cost preference
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['premium'] & service_match['medium'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['premium'] & (service_match['low'] | proximity_match['far']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['premium'] & service_match['low'] & proximity_match['far'] & quality['low'], recommendation['low'])
    ]

    recommender_ctrl = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(recommender_ctrl)

def compute_recommendation_score(row, user_service, user_cost_pref, user_quality_pref, fuzzy_system, user_coords):
    try:
        service_score = compute_service_match(user_service, row["Services"])
        cost_value = map_cost_rating(row["Cost Level"])
        quality_value = float(row["Quality Score"]) if pd.notna(row["Quality Score"]) else 3.0
        hospital_coords = row["Coordinates"]
        distance = haversine_distance(user_coords, hospital_coords)
        proximity_score = max(0, 1 - (distance / MAX_DISTANCE))  # Normalize to 0-1, 0 at MAX_DISTANCE

        fuzzy_system.input["cost"] = cost_value
        fuzzy_system.input["quality"] = quality_value
        fuzzy_system.input["service_match"] = service_score
        fuzzy_system.input["proximity_match"] = proximity_score

        fuzzy_system.compute()
        score = fuzzy_system.output.get("recommendation", 0.0)
        logger.info(f"Hospital: {row['Name']}, Service Match: {service_score:.2f}, Proximity Score: {proximity_score:.2f}, Cost: {cost_value:.2f}, Quality: {quality_value:.2f}, Score: {score:.3f}")
        return score
    except Exception as e:
        logger.error(f"Error processing {row['Name']}: {e}")
        return 0.0

def recommend_hospitals(location, user_service, cost_pref_str, quality_pref_str):
    """
    Generate hospital recommendations with an interactive map.
    
    Args:
        location (str): Preferred city or address (e.g., 'Ikorodu')
        user_service (str): Desired service (e.g., 'Surgery')
        cost_pref_str (str): Cost preference ('Low', 'Medium', 'High')
        quality_pref_str (str): Quality preference ('Low', 'Medium', 'High')
    
    Returns:
        tuple: (pd.DataFrame of recommendations, str path to map_output.html or None)
    """
    try:
        logger.info("Loading dataset Lagos_hospital.csv")
        dataset_path = "Lagos_hospital.csv"
        if not os.path.exists(dataset_path):
            logger.error(f"Dataset not found at {dataset_path}")
            raise FileNotFoundError(f"Dataset not found at {dataset_path}")
        data = pd.read_csv(dataset_path)
        data = data.dropna(subset=["Name", "Services", "Cost Level", "Quality Score", "User Rating"])
        data["Full Address"] = data["Full Address"].fillna("Unknown")
        data["Quality Score"] = pd.to_numeric(data["Quality Score"], errors="coerce").fillna(3.0)
        data["User Rating"] = pd.to_numeric(data["User Rating"], errors="coerce").fillna(3.0)

        cost_pref_str = get_valid_category(cost_pref_str, "Medium")
        quality_pref_str = get_valid_category(quality_pref_str, "High")
        cost_pref_value = map_preference_to_value(cost_pref_str)
        quality_pref_value = map_preference_to_value(quality_pref_str)

        # Extract user city from location
        user_city = extract_city(location)
        logger.info(f"User city extracted: {user_city}")

        # Extract hospital cities
        data["City"] = data["Full Address"].apply(extract_city)
        logger.info(f"Unique hospital cities: {data['City'].unique()}")

        # Geocode for proximity and map
        cache_file = "hospital_coordinates.csv"
        geocode_cache = load_geocode_cache(cache_file)
        user_coords = geocode_address(location, geocode_cache)
        data["Coordinates"] = data["Full Address"].apply(lambda addr: geocode_address(addr, geocode_cache))
        save_geocode_cache(geocode_cache, cache_file)

        fuzzy_system = setup_fuzzy_system()
        data["Recommendation_Score"] = data.apply(
            lambda row: compute_recommendation_score(row, user_service, cost_pref_str, quality_pref_str, fuzzy_system, user_coords),
            axis=1
        )

        recommendations = data[data["Recommendation_Score"] > 0].copy()
        if recommendations.empty:
            logger.warning(f"No hospitals found matching service '{user_service}'")
            return pd.DataFrame(), None

        recommendations = recommendations.sort_values(by="Recommendation_Score", ascending=False).head(3)

        # Add routing information (placeholder since OSM routing isn't integrated)
        for idx, row in recommendations.iterrows():
            distance, duration, instructions = get_driving_route(
                user_coords, row["Coordinates"], row["Name"]
            )
            recommendations.at[idx, "Route_Distance"] = distance
            recommendations.at[idx, "Route_Duration"] = duration
            recommendations.at[idx, "Route_Instructions"] = instructions if instructions else "N/A"

        # Generate interactive map
        map_file = generate_map_html(recommendations, user_coords, user_service, location)

        recommendations.to_csv("recommended_hospitals.csv", index=False)
        logger.info("Recommendations saved to recommended_hospitals.csv")

        return recommendations[
            [
                "Name", "Full Address", "Services", "Cost Level", "Quality Score",
                "Recommendation_Score", "Route_Distance", "Route_Duration", "Route_Instructions"
            ]
        ], map_file
    except Exception as e:
        logger.error(f"Error in recommendation: {e}")
        return pd.DataFrame(), None