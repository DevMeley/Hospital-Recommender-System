# app.py

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from hospital_recommender import recommend_hospitals
import pandas as pd
import os

app = FastAPI(title="Hospital Recommender API")

# === CORS (only needed in dev when frontend runs on Vite/CRA server) ===
origins = [
    "http://localhost:5173",   
    "http://localhost:3000",   
    "https://hopsital-recommendation-system.vercel.app",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === Models ===
class RecommendationRequest(BaseModel):
    location: str
    service_needed: str
    cost_preference: str
    quality_preference: str

class RecommendationResponse(BaseModel):
    name: str
    full_address: str
    services: str
    cost_level: str
    quality_score: float
    recommendation_score: float
    route_distance: str | None
    route_duration: str | None
    route_instructions: str | None

# === API ROUTES ===
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/api/recommend")  # <- put under /api
async def get_recommendations(request: RecommendationRequest):
    try:
        valid_categories = {"Low", "Medium", "High"}
        cost_pref = request.cost_preference.capitalize()
        quality_pref = request.quality_preference.capitalize()
        if cost_pref not in valid_categories:
            raise HTTPException(status_code=400, detail="Invalid cost preference. Must be Low, Medium, or High.")
        if quality_pref not in valid_categories:
            raise HTTPException(status_code=400, detail="Invalid quality preference. Must be Low, Medium, or High.")

        dataset_path = os.path.join(os.path.dirname(__file__), "Lagos_hospital.csv")
        if not os.path.exists(dataset_path):
            raise HTTPException(status_code=500, detail="Hospital dataset not found.")

        try:
            df = pd.read_csv(dataset_path)
            required_columns = ["Name", "Full Address", "Services", "Cost Level", "Quality Score", "User Rating"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                raise HTTPException(status_code=500, detail=f"Dataset missing required columns: {missing_columns}")
        except pd.errors.ParserError:
            raise HTTPException(status_code=500, detail="Invalid CSV format in Lagos_hospital.csv.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error reading dataset: {str(e)}")

        recommendations, map_file = recommend_hospitals(
            location=request.location,
            user_service=request.service_needed,
            cost_pref_str=cost_pref,
            quality_pref_str=quality_pref
        )

        if recommendations.empty:
            raise HTTPException(status_code=404, detail="No hospitals found matching your criteria.")

        response = [
            RecommendationResponse(
                name=row["Name"],
                full_address=row["Full Address"],
                services=row["Services"],
                cost_level=row["Cost Level"],
                quality_score=row["Quality Score"],
                recommendation_score=row["Recommendation_Score"],
                route_distance=row.get("Route_Distance"),
                route_duration=row.get("Route_Duration"),
                route_instructions=row.get("Route_Instructions")
            )
            for _, row in recommendations.iterrows()
        ]

        map_url = f"/map" if map_file else None
        return {"recommendations": response, "map_url": map_url}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# === SERVE FRONTEND BUILD ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Path to Vite's dist folder
FRONTEND_DIST = os.path.join(BASE_DIR, "..", "Hopsital Recommender-Client", "dist")

# Mount Vite build output if it exists
if os.path.exists(FRONTEND_DIST):
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="Hospital Recommender-Client")
else:
    print("Vite dist folder not found. Did you run `npm run build` inside Hospital Recommender-Client?")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
