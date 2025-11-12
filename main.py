import os
import random
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, conlist, confloat

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class FlipRequest(BaseModel):
    base_price: confloat(gt=0) = Field(..., description="Base price before flip")
    win_odds: confloat(gt=0, lt=1) = 0.9
    # Pydantic v2: conlist uses min_length/max_length (not min_items/max_items)
    discount_range: conlist(confloat(gt=0, lt=1), min_length=2, max_length=2) = [0.1, 0.25]
    surcharge_range: conlist(confloat(gt=0, lt=1), min_length=2, max_length=2) = [0.2, 0.25]


class FlipResult(BaseModel):
    outcome: Literal["win", "lose"]
    adjustment_percent: float
    final_price: float
    roll: float
    seed: str
    timestamp: str
    terms_version: str = "1.0"


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.post("/api/flip", response_model=FlipResult)
def flip_coin(payload: FlipRequest):
    # Validate ranges
    d_min, d_max = payload.discount_range
    s_min, s_max = payload.surcharge_range
    if d_min >= d_max:
        raise HTTPException(status_code=400, detail="discount_range must be [min, max]")
    if s_min >= s_max:
        raise HTTPException(status_code=400, detail="surcharge_range must be [min, max]")

    seed = str(uuid.uuid4())
    roll = random.random()

    if roll < payload.win_odds:
        # Win path: choose a random discount between range
        pct = random.uniform(d_min, d_max)
        final = round(payload.base_price * (1 - pct), 2)
        outcome: Literal["win", "lose"] = "win"
        adj = pct
    else:
        # Lose path: apply random surcharge between range
        pct = random.uniform(s_min, s_max)
        final = round(payload.base_price * (1 + pct), 2)
        outcome = "lose"
        adj = pct

    return FlipResult(
        outcome=outcome,
        adjustment_percent=round(adj, 4),
        final_price=final,
        roll=round(roll, 6),
        seed=seed,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    
    try:
        # Try to import database module
        from database import db
        
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            
            # Try to list collections to verify connectivity
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]  # Show first 10 collections
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
            
    except ImportError:
        response["database"] = "❌ Database module not found (run enable-database first)"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"
    
    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
