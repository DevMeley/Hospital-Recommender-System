import pandas as pd
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import os
import logging
import re
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import matplotlib.pyplot as plt
import folium

# Setup logging
logging.basicConfig(filename='hospital_recommender.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default coordinates (Lagos center)
DEFAULT_COORDS = (6.5244, 3.3792)

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
    if address in cache and cache[address] != "None":
        try:
            # Use cached coordinates if valid
            lat, lon = map(float, cache[address].strip('()').split(','))
            logger.info(f"Using cached coordinates for {address}: {cache[address]}")
            return (lat, lon)
        except (ValueError, AttributeError):
            logger.warning(f"Cached coordinates for '{address}' are invalid. Re-geocoding.")
    # Geocode anew if not in cache or invalid
    try:
        geolocator = Nominatim(user_agent="hospital_recommender")
        full_address = f"{address}, Lagos, Nigeria"
        location = geolocator.geocode(full_address)
        if location:
            coords = (location.latitude, location.longitude)
            cache[address] = f"({coords[0]},{coords[1]})"
            save_geocode_cache(cache)
            return coords
        cache[address] = "None"
        return DEFAULT_COORDS
    except Exception as e:
        logger.error(f"Geocoding error for '{address}': {e}")
        cache[address] = "None"
        return DEFAULT_COORDS

def get_driving_route(user_coords, hospital_coords, hospital_name):
    if user_coords == DEFAULT_COORDS or hospital_coords == DEFAULT_COORDS:
        return None, None, None
    try:
        distance = geodesic(user_coords, hospital_coords).km
        duration = distance / 30 * 3600  # Estimate: 30 km/h in Lagos
        duration_text = f"{int(duration // 3600)}h {int((duration % 3600) // 60)}m"
        distance_text = f"{distance:.1f} km"
        return distance_text, duration_text, "Estimated driving route"
    except Exception as e:
        logger.error(f"Error estimating route to {hospital_name}: {e}")
        return None, None, None

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

def setup_fuzzy_system():
    cost = ctrl.Antecedent(np.arange(1, 3.1, 0.1), 'cost')
    quality = ctrl.Antecedent(np.arange(2, 5.1, 0.1), 'quality')
    service_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'service_match')
    location_match = ctrl.Antecedent(np.arange(0, 1.01, 0.01), 'location_match')
    recommendation = ctrl.Consequent(np.arange(0, 1.01, 0.01), 'recommendation')

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

    location_match['low'] = fuzz.trimf(location_match.universe, [0, 0, 0.5])
    location_match['medium'] = fuzz.trimf(location_match.universe, [0.3, 0.5, 0.7])
    location_match['high'] = fuzz.trimf(location_match.universe, [0.5, 1, 1])

    recommendation['low'] = fuzz.trimf(recommendation.universe, [0, 0, 0.4])
    recommendation['medium'] = fuzz.trimf(recommendation.universe, [0.3, 0.5, 0.6])
    recommendation['high'] = fuzz.trimf(recommendation.universe, [0.7, 0.85, 1])

    rules = [
        ctrl.Rule(cost['low'] & service_match['high'] & location_match['high'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & location_match['high'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['high'] & location_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['low'] & service_match['medium'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['low'] & service_match['medium'] & location_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['low'] & (service_match['low'] | location_match['low']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['low'] & service_match['low'] & location_match['low'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['high'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['high'] & location_match['high'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['high'] & location_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & service_match['medium'] & location_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['medium'] & (service_match['low'] | location_match['low']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['medium'] & service_match['low'] & location_match['low'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['high'] & service_match['high'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['high'] & location_match['high'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['high'] & location_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['high'] & service_match['medium'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['high'] & service_match['medium'] & location_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['high'] & (service_match['low'] | location_match['low']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['high'] & service_match['low'] & location_match['low'] & quality['low'], recommendation['low']),
        ctrl.Rule(cost['premium'] & service_match['high'] & location_match['high'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & location_match['high'] & quality['medium'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['high'] & location_match['medium'] & quality['high'], recommendation['high']),
        ctrl.Rule(cost['premium'] & service_match['medium'] & location_match['high'] & quality['high'], recommendation['medium']),
        ctrl.Rule(cost['premium'] & service_match['medium'] & location_match['medium'] & quality['medium'], recommendation['medium']),
        ctrl.Rule(cost['premium'] & (service_match['low'] | location_match['low']) & quality['high'], recommendation['low']),
        ctrl.Rule(cost['premium'] & service_match['low'] & location_match['low'] & quality['low'], recommendation['low'])
    ]

    recommender_ctrl = ctrl.ControlSystem(rules)
    return ctrl.ControlSystemSimulation(recommender_ctrl)

def compute_recommendation_score(row, user_service, user_cost_pref, user_quality_pref, fuzzy_system):
    try:
        service_score = compute_service_match(user_service, row["Services"])
        cost_value = map_cost_rating(row["Cost Level"])
        quality_value = float(row["Quality Score"]) if pd.notna(row["Quality Score"]) else 3.0
        location_score = row["Location_Match"]

        fuzzy_system.input["cost"] = cost_value
        fuzzy_system.input["quality"] = quality_value
        fuzzy_system.input["service_match"] = service_score
        fuzzy_system.input["location_match"] = location_score

        fuzzy_system.compute()
        score = fuzzy_system.output.get("recommendation", 0.0)
        logger.info(f"Hospital: {row['Name']}, Service Match: {service_score:.2f}, Location Match: {location_score:.2f}, Cost: {cost_value:.2f}, Quality: {quality_value:.2f}, Score: {score:.3f}")
        return score
    except Exception as e:
        logger.error(f"Error processing {row['Name']}: {e}")
        return 0.0


def plot_map(recommendations):
    if recommendations.empty:
        print("No hospitals to display on the map.")
        return

    coordinates = []
    for coord in recommendations['Coordinates']:
        # Accept tuple/list of floats, or parse from string if needed
        if isinstance(coord, (tuple, list)) and len(coord) == 2:
            try:
                lat, lng = float(coord[0]), float(coord[1])
                coordinates.append((lat, lng))
            except Exception:
                print(f"Skipping invalid coordinate: {coord}")
        elif isinstance(coord, str):
            try:
                lat, lng = map(float, coord.strip('()').split(','))
                coordinates.append((lat, lng))
            except Exception:
                print(f"Skipping invalid coordinate: {coord}")
        else:
            print(f"Skipping invalid coordinate: {coord}")

    if not coordinates:
        print("Error: No valid coordinates found in the recommendations.")
        return

    map_center = coordinates[0]
    m = folium.Map(location=map_center, zoom_start=12)

    for idx, (coord, row) in enumerate(zip(coordinates, recommendations.itertuples())):
        folium.Marker(
            location=coord,
            popup=f"Name: {getattr(row, 'Name', 'Unknown Hospital')}<br>Score: {getattr(row, 'Recommendation_Score', 'N/A'):.2f}",
            icon=folium.Icon(color='blue', icon='hospital')
        ).add_to(m)

    map_path = 'hospital_map.html'
    m.save(map_path)
    print("Map saved as hospital_map.html for frontend integration.")
    return map_path

def recommend_hospitals(location, user_service, cost_pref_str, quality_pref_str):
    """
    Generate hospital recommendations based on user inputs.
    
    Args:
        location (str): Preferred city or address (e.g., 'Ikorodu')
        user_service (str): Desired service (e.g., 'Surgery')
        cost_pref_str (str): Cost preference ('Low', 'Medium', 'High')
        quality_pref_str (str): Quality preference ('Low', 'Medium', 'High')
    
    Returns:
        tuple: (pd.DataFrame of recommendations, str path to map file)
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

        # Compute Location_Match
        data["Location_Match"] = data["City"].apply(lambda city: 1.0 if city.lower() == user_city.lower() else 0.0)
        data = data[data["Location_Match"] == 1.0]
        if data.empty:
            logger.warning(f"No hospitals found in city '{user_city}'")
            return pd.DataFrame(), None

        # Geocode for routing and map
        cache_file = "hospital_coordinates.csv"
        geocode_cache = load_geocode_cache(cache_file)
        user_coords = geocode_address(location, geocode_cache)
        data["Coordinates"] = data["Full Address"].apply(lambda addr: geocode_address(addr, geocode_cache))
        save_geocode_cache(geocode_cache, cache_file)

        fuzzy_system = setup_fuzzy_system()
        data["Recommendation_Score"] = data.apply(
            lambda row: compute_recommendation_score(row, user_service, cost_pref_str, quality_pref_str, fuzzy_system),
            axis=1
        )

        recommendations = data[data["Recommendation_Score"] > 0].copy()
        if recommendations.empty:
            logger.warning(f"No hospitals found matching service '{user_service}'")
            return pd.DataFrame(), None

        recommendations = recommendations.sort_values(by="Recommendation_Score", ascending=False).head(3)

        # Add routing information
        for idx, row in recommendations.iterrows():
            distance, duration, instructions = get_driving_route(
                user_coords, row["Coordinates"], row["Name"]
            )
            recommendations.at[idx, "Route_Distance"] = distance
            recommendations.at[idx, "Route_Duration"] = duration
            recommendations.at[idx, "Route_Instructions"] = instructions if instructions else "N/A"

        recommendations.to_csv("recommended_hospitals.csv", index=False)
        logger.info("Recommendations saved to recommended_hospitals.csv")

        # Generate visualizations
        map_file = plot_map(recommendations)

        return recommendations[
            [
                "Name", "Full Address", "Services", "Cost Level", "Quality Score",
                "Recommendation_Score", "Route_Distance", "Route_Duration", "Route_Instructions","Coordinates"
            ]
        ], map_file
    except Exception as e:
        logger.error(f"Error in recommendation: {e}")
        return pd.DataFrame(), None

if __name__ == "__main__":
    recs, map_file = recommend_hospitals("Ikeja", "general medicine", "Medium", "High")
    print(f"Recommendations: {recs}")
    print(f"Map file: {map_file}")