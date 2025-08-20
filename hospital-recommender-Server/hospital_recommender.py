# recommender.py

import pandas as pd
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import os
import logging
import re
from math import radians, sin, cos, sqrt, atan2
import requests
from jinja2 import Template
from typing import Tuple, Optional, Dict

# Setup logging
logging.basicConfig(filename='hospital_recommender.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default coordinates (Lagos center)
DEFAULT_COORDS = (6.5244, 3.3792)

# Maximum distance threshold for proximity (in km)
MAX_DISTANCE = 15.0

def get_valid_category(value: str, default: str) -> str:
    """Validate and normalize category input."""
    valid_options = {"low", "medium", "high"}
    value = value.strip().lower() if value else default.lower()
    return value.capitalize() if value in valid_options else default.capitalize()

def map_preference_to_value(pref: str) -> float:
    """Map preference to a normalized value."""
    pref_map = {"Low": 0.33, "Medium": 0.66, "High": 1.0}
    return pref_map.get(pref, 0.33)

def compute_service_match(user_service: str, hospital_services: str) -> float:
    """Compute service match score with detailed logic."""
    if pd.isna(hospital_services) or pd.isna(user_service):
        logger.warning('Missing service data')
        return 0.0
    user_service = user_service.lower().strip()
    hospital_services = hospital_services.lower().strip()
    hospital_service_list = [s.strip() for s in hospital_services.split(',')]
    if user_service == 'surgery':
        if any(svc in hospital_service_list for svc in ['surgery', 'surgical services']):
            if not any(exc in hospital_service_list for exc in ['dental surgery', 'oral surgery', 'cosmetic surgery']):
                logger.info(f'Exact match for "surgery" in {hospital_service_list}')
                return 1.0
            logger.info(f'Excluded mismatch for "surgery" in {hospital_service_list}')
            return 0.0
        elif any('surgery' in svc and not any(exc in svc for exc in ['dental', 'oral', 'cosmetic']) 
                 for svc in hospital_service_list):
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

def map_cost_rating(cost_rating: str) -> float:
    """Map cost rating to a numerical value."""
    if pd.isna(cost_rating) or cost_rating == 'N/A':
        return 1.0
    cost_map = {"Low": 1.0, "Medium": 2.0, "High": 3.0, "Premium": 3.0}
    return cost_map.get(cost_rating.strip().capitalize(), 1.0)

def load_geocode_cache(cache_file: str = "hospital_coordinates.csv") -> dict:
    """Load geocoding cache from CSV."""
    if os.path.exists(cache_file):
        try:
            cache = pd.read_csv(cache_file, index_col="Address").to_dict()["Coordinates"]
            return {k: v for k, v in cache.items() if v != "None"}
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
    return {}

def save_geocode_cache(cache: dict, cache_file: str = "hospital_coordinates.csv") -> None:
    """Save geocoding cache to CSV."""
    try:
        cache_df = pd.DataFrame.from_dict(cache, orient="index", columns=["Coordinates"])
        cache_df.index.name = "Address"
        cache_df.to_csv(cache_file)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def geocode_address(address: str, cache: dict) -> tuple:
    """Geocode an address using Nominatim with caching."""
    if address in cache:
        coords_str = cache[address]
        try:
            lat, lon = map(float, coords_str.strip("()").split(","))
            return (lat, lon)
        except:
            logger.warning(f"Invalid cached coordinates for '{address}'. Re-geocoding.")

    try:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}, Lagos, Nigeria"
        headers = {'User-Agent': 'HospitalRecommender/1.0 (your.email@example.com)'}  # Replace with your contact
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        if response.json():
            location = response.json()[0]
            coords = (float(location["lat"]), float(location["lon"]))
            cache[address] = f"({coords[0]},{coords[1]})"
            save_geocode_cache(cache)
            return coords
        logger.warning(f"No coordinates found for '{address}'")
        cache[address] = "None"
        save_geocode_cache(cache)
        return DEFAULT_COORDS
    except requests.exceptions.RequestException as e:
        logger.error(f"Geocoding error for '{address}': {e}")
        cache[address] = "None"
        save_geocode_cache(cache)
        return DEFAULT_COORDS

def haversine_distance(coord1: tuple, coord2: tuple) -> float:
    """Calculate straight-line distance between two coordinates in kilometers."""
    lat1, lon1 = radians(coord1[0]), radians(coord1[1])
    lat2, lon2 = radians(coord2[0]), radians(coord2[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return 6371 * c  # Earth radius in kilometers

def extract_city(address: str) -> str:
    """Extract city from address using regex."""
    cities = (
        r'Ikorodu|Ikoyi|Ikeja|Victoria Island|Surulere|Badagry|Lagos Island|Agege|'
        r'Alimosho|Apapa|Epe|Eti-Osa|Ibeju-Lekki|Ifako-Ijaiye|Kosofe|Lagos Mainland|'
        r'Mushin|Ojo|Oshodi-Isolo|Shomolu|Ajeromi-Ifelodun|Amuwo-Odofin|'
        r'Lekki|Ajah|Yaba|Gbagada|Maryland|Ilupeju|Ketu|Magodo|Ojota|Egbeda|'
        r'Idimu|Ipaja|Bariga|Festac Town|Amuwo|Isolo|Okota|Ikotun|Ogudu|'
        r'Alagbado|Ojodu|Iju|Akoka|Somolu|Agidingbi|Ogba|Isheri|Agbara|Ijanikin'
    )
    match = re.search(f'({cities})', address, re.IGNORECASE)
    return match.group(1).lower() if match else 'unknown'

def generate_map_html(recommendations: pd.DataFrame, user_coords: tuple, user_service: str, location: str) -> str:
    """Generate HTML with an interactive OpenStreetMap using Leaflet, including static markers."""
    # Fallback to static locations if recommendations are empty or for simplicity
    if recommendations.empty:
        logger.warning("No recommendations available, using static locations")
        static_locations = [
            {"name": "Aruna Ogun Memorial Specialist Hospital", "lat": 6.6191, "lng": 3.5105},
            {"name": "Ikeja General Hospital", "lat": 6.5982, "lng": 3.3392},
            {"name": "Lagos Island General Hospital", "lat": 6.4474, "lng": 3.3922}
        ]
    else:
        static_locations = [
            {"name": row["Name"], "lat": row["Coordinates"][0], "lng": row["Coordinates"][1]}
            for _, row in recommendations.head(3).iterrows()
        ]

    center_lat, center_lng = user_coords if user_coords != DEFAULT_COORDS else 6.5244, 3.3792
    
    template = Template("""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
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
            </tr>
            {% if recommendations %}
                {% for rec in recommendations %}
                <tr>
                    <td>{{ rec.Name }}</td>
                    <td><span class="address-link" onclick="panToHospital({{ rec.Coordinates[0] }}, {{ rec.Coordinates[1] }}, '{{ rec.Name | replace("'", "\\'") }}')">{{ rec.Full Address }}</span></td>
                    <td>{{ rec.Services }}</td>
                    <td>{{ rec.Cost Level }}</td>
                    <td>{{ rec.Quality Score }}</td>
                    <td>{{ rec.Recommendation_Score }}</td>
                </tr>
                {% endfor %}
            {% else %}
                <tr><td colspan="6">No recommendations available.</td></tr>
            {% endif %}
        </table>
        <script>
            let map = L.map('map').setView([{ center_lat }, { center_lng }], 10);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                maxZoom: 19,
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            }).addTo(map);
            let markers = [];
            {% for loc in static_locations %}
            let marker = L.marker([{{ loc.lat }}, {{ loc.lng }}]).addTo(map)
                .bindPopup(`<b>{{ loc.name | replace("'", "\\'") }}</b>`);
            markers.push({marker: marker, name: '{{ loc.name | replace("'", "\\'") }}'});
            {% endfor %}
            function panToHospital(lat, lng, name) {
                map.setView([lat, lng], 15);
                markers.forEach(m => {
                    if (m.name === name) m.marker.openPopup();
                    else m.marker.closePopup();
                });
            }
        </script>
    </body>
    </html>
    """)
    
    html_content = template.render(
        recommendations=recommendations.to_dict(orient='records') if not recommendations.empty else None,
        static_locations=static_locations,
        service=user_service,
        location=location or "Lagos",
        center_lat=center_lat,
        center_lng=center_lng
    )
    
    return html_content  # Return HTML content instead of file path

def setup_fuzzy_system() -> ctrl.ControlSystemSimulation:
    """Set up the fuzzy logic system with all 36 rules."""
    cost = ctrl.Antecedent(np.arange(1, 3.1, 0.1), 'cost')
    quality = ctrl.Antecedent(np.arange(2, 5.1, 0.1), 'quality')
    service_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'service_match')
    proximity_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'proximity_match')
    recommendation = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'recommendation')

    # Membership functions
    cost['low'] = fuzz.trimf(cost.universe, [1, 1, 1.5])
    cost['medium'] = fuzz.trimf(cost.universe, [1.2, 1.75, 2.5])
    cost['high'] = fuzz.trimf(cost.universe, [2, 2.5, 3])
    cost['premium'] = fuzz.trimf(cost.universe, [2.5, 3, 3])

    quality['low'] = fuzz.trimf(quality.universe, [2, 2, 3])
    quality['medium'] = fuzz.trimf(quality.universe, [2.5, 3.5, 4.5])
    quality['high'] = fuzz.trimf(quality.universe, [4, 4.5, 5])

    service_match['low'] = fuzz.trimf(service_match.universe, [0, 0, 0.4])
    service_match['medium'] = fuzz.trimf(service_match.universe, [0.3, 0.6, 0.8])
    service_match['high'] = fuzz.trimf(service_match.universe, [0.7, 1, 1])

    proximity_match['far'] = fuzz.trimf(proximity_match.universe, [0, 0, 0.3])
    proximity_match['medium'] = fuzz.trimf(proximity_match.universe, [0.2, 0.5, 0.8])
    proximity_match['close'] = fuzz.trimf(proximity_match.universe, [0.7, 1, 1])

    recommendation['low'] = fuzz.trimf(recommendation.universe, [0, 0, 0.4])
    recommendation['medium'] = fuzz.trimf(recommendation.universe, [0.3, 0.6, 0.8])
    recommendation['high'] = fuzz.trimf(recommendation.universe, [0.7, 0.9, 1])

    # All 36 fuzzy rules
    rules = [
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['close'] & quality['low'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['medium'] & quality['low'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['far'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['high'] & proximity_match['far'] & quality['medium'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['close'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['close'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['medium'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['medium'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['medium'] & proximity_match['far'] & quality['high'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['low'] & proximity_match['close'] & quality['high'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['close'] & quality['low'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['medium'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['high'] & proximity_match['far'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & proximity_match['close'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['close'] & quality['low'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['high'] & proximity_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['medium'] & proximity_match['close'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['close'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['close'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & proximity_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['medium'] & proximity_match['close'] & quality['high'], recommendation['medium']),
    ]

    recommender_ctrl = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(recommender_ctrl)

def compute_recommendation_score(row: pd.Series, user_service: str, user_cost_pref: str, 
                               user_quality_pref: str, fuzzy_system: ctrl.ControlSystemSimulation, 
                               user_coords: tuple) -> float:
    """Compute recommendation score using fuzzy logic."""
    try:
        service_score = compute_service_match(user_service, row["Services"])
        cost_value = map_cost_rating(row["Cost Level"])
        quality_value = float(row["Quality Score"]) if pd.notna(row["Quality Score"]) else 3.0
        hospital_coords = row["Coordinates"]
        distance = haversine_distance(user_coords, hospital_coords)
        proximity_score = max(0, 1 - min(distance / MAX_DISTANCE, 1))

        fuzzy_system.input["cost"] = cost_value
        fuzzy_system.input["quality"] = quality_value
        fuzzy_system.input["service_match"] = service_score
        fuzzy_system.input["proximity_match"] = proximity_score

        fuzzy_system.compute()
        score = fuzzy_system.output.get("recommendation", 0.0)
        logger.info(f"Hospital: {row['Name']}, Service: {service_score:.2f}, Proximity: {proximity_score:.2f}, "
                    f"Cost: {cost_value:.2f}, Quality: {quality_value:.2f}, Score: {score:.3f}")
        return score
    except Exception as e:
        logger.error(f"Error processing {row['Name']}: {e}")
        return 0.0

def recommend_hospitals(location: str, user_service: str, cost_pref_str: str, 
                      quality_pref_str: str) -> Tuple[pd.DataFrame, str]:
    """
    Generate hospital recommendations with an embedded map.
    
    Args:
        location (str): User-provided address or city
        user_service (str): Desired service
        cost_pref_str (str): Cost preference
        quality_pref_str (str): Quality preference
    
    Returns:
        tuple: (pd.DataFrame of recommendations, HTML content with map)
    """
    try:
        logger.info(f"Loading dataset Lagos_hospital.csv for location: {location}")
        dataset_path = "Lagos_hospital.csv"
        if not os.path.exists(dataset_path):
            logger.error(f"Dataset not found at {dataset_path}")
            raise FileNotFoundError(f"Dataset not found at {dataset_path}")

        data = pd.read_csv(dataset_path)
        required_columns = ["Name", "Full Address", "Services", "Cost Level", "Quality Score"]
        if not all(col in data.columns for col in required_columns):
            missing = [col for col in required_columns if col not in data.columns]
            logger.error(f"Missing columns in dataset: {missing}")
            raise ValueError(f"Dataset missing columns: {missing}")

        data = data.dropna(subset=required_columns)
        data["Quality Score"] = pd.to_numeric(data["Quality Score"], errors="coerce").fillna(3.0)

        cost_pref_str = get_valid_category(cost_pref_str, "Medium")
        quality_pref_str = get_valid_category(quality_pref_str, "High")

        # Geocode user location
        geocode_cache = load_geocode_cache()
        user_coords = geocode_address(location, geocode_cache)

        # Geocode hospital addresses
        data["Coordinates"] = data["Full Address"].apply(lambda addr: geocode_address(addr, geocode_cache))
        save_geocode_cache(geocode_cache)

        fuzzy_system = setup_fuzzy_system()
        data["Recommendation_Score"] = data.apply(
            lambda row: compute_recommendation_score(row, user_service, cost_pref_str, quality_pref_str, 
                                                  fuzzy_system, user_coords), axis=1
        )

        recommendations = data[data["Recommendation_Score"] > 0].copy()
        if recommendations.empty:
            logger.warning(f"No hospitals found matching service '{user_service}' near '{location}'")
            recommendations = pd.DataFrame()  # Empty DataFrame for fallback

        recommendations = recommendations.sort_values(by="Recommendation_Score", ascending=False).head(3)

        # Generate HTML with embedded map
        map_html = generate_map_html(recommendations, user_coords, user_service, location or "Lagos")

        recommendations.to_csv("recommended_hospitals.csv", index=False)
        logger.info("Recommendations saved to recommended_hospitals.csv")

        return recommendations[
            ["Name", "Full Address", "Services", "Cost Level", "Quality Score", "Recommendation_Score"]
        ], map_html
    except Exception as e:
        logger.error(f"Error in recommendation process: {e}")
        return pd.DataFrame(), generate_map_html(pd.DataFrame(), DEFAULT_COORDS, user_service, location or "Lagos")