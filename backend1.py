from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from typing import Dict, List, Optional, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
import os
from genai_utils import get_llm_price_suggestion

# Load environment variables
load_dotenv()

# FastAPI app setup
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["JSONS"]
collections = ["reliance", "pai", "croma", "flipkart"]

# Set up LLM with memory for LangChain integration
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", google_api_key=os.getenv("GOOGLE_API_KEY"))
memory = ConversationBufferMemory(memory_key="chat_history")

# Prompt template for pricing assistant
template = """
You are a pricing assistant. Given the following laptop details:
{details}

Suggest the best price and reasoning:
"""

prompt = PromptTemplate(template=template, input_variables=["details"])

# Chain with memory
chain = LLMChain(llm=llm, prompt=prompt, memory=memory)

# Brand tiers for pricing strategy (all lowercase for consistent comparison)
brand_tiers = {
    "premium": ["apple"],
    "budget": ["avita", "infinix", "jiocloud", "chuwi"],
    "mid": ["acer", "asus", "dell", "hp", "lenovo"]
}

# Platform adjustment factors (platform-specific strategy)
platform_factors = {
    "reliance": 1.00,
    "pai": 0.97,
    "croma": 1.03,
    "flipkart": 0.95
}

def get_brand_tier(brand):
    """Determine brand tier using case-insensitive comparison"""
    brand_lower = brand.lower()
    for tier, brands in brand_tiers.items():
        if any(b == brand_lower for b in brands):
            return tier
    return "mid"  # Default to mid tier if not found

# Function to find products based on filters
def find_products(brand, ram, storage, processor_series):
    """Find products with case-insensitive search"""
    # Basic query with case-insensitive search
    query = {
        "Brand": {"$regex": f"^{brand.strip()}$", "$options": "i"},
        "RAM": {"$regex": f"^{ram.strip()}$", "$options": "i"},
        "Storage": {"$regex": f"^{storage.strip()}$", "$options": "i"},
    }

    # Adjust processor query based on brand
    if brand.lower() == "apple":
        query["Processor Series"] = {"$regex": f"^{processor_series.strip()}$", "$options": "i"}
    else:
        query["$or"] = [
            {"Processor Type": {"$regex": f"^{processor_series.strip()}$", "$options": "i"}},
            {"Processor Series": {"$regex": f"^{processor_series.strip()}$", "$options": "i"}}
        ]

    results = {}
    similar_products = {}
    platform_prices = {}
    avg_prices_by_platform = {}
    price_breakdown = {}

    for coll in collections:
        exact_match = list(db[coll].find(query, {
            "_id": 0, "Product Name": 1, "Processor Type": 1,
            "Processor Series": 1, "Price": 1, "MRP": 1, "RAM": 1,
            "Storage": 1, "Brand": 1
        }))

        if exact_match:
            results[coll] = exact_match
            prices = [prod["Price"] for prod in exact_match if "Price" in prod]
            platform_prices[coll] = prices
            if prices:
                avg_prices_by_platform[coll] = sum(prices) / len(prices)
        else:
            # Find similar products with different brands but same specs
            similar_query = {
                "RAM": {"$regex": f"^{ram.strip()}$", "$options": "i"},
                "Storage": {"$regex": f"^{storage.strip()}$", "$options": "i"},
                "Brand": {"$not": {"$regex": f"^{brand.strip()}$", "$options": "i"}}  # Different brand
            }

            # Add processor conditions
            if brand.lower() == "apple":
                similar_query["Processor Series"] = {"$regex": f"^{processor_series.strip()}$", "$options": "i"}
            else:
                similar_query["$or"] = [
                    {"Processor Type": {"$regex": f"^{processor_series.strip()}$", "$options": "i"}},
                    {"Processor Series": {"$regex": f"^{processor_series.strip()}$", "$options": "i"}}
                ]

            similar_match = list(db[coll].find(similar_query, {
                "_id": 0, "Brand": 1, "Product Name": 1, "Processor Type": 1,
                "Processor Series": 1, "Price": 1, "MRP": 1, "RAM": 1, "Storage": 1
            }).limit(5))  # Limit to 5 similar products for better performance

            if similar_match:
                similar_products[coll] = similar_match

            results[coll] = "Not Available"

    # Determine brand tier for price suggestion
    tier = get_brand_tier(brand)
    brand_factor = {
        "premium": 1.05,
        "mid": 1.00,
        "budget": 0.95
    }[tier]

    suggested_prices = {}
    for platform in collections:
        if results.get(platform) == "Not Available":
            ref_platforms = [p for p in avg_prices_by_platform if p != platform]
            if ref_platforms:
                avg_price = sum(avg_prices_by_platform[p] for p in ref_platforms) / len(ref_platforms)
                platform_factor = platform_factors.get(platform, 1.00)
                combined_factor = brand_factor * platform_factor
                suggested = round(avg_price * combined_factor, 2)
                suggested_prices[platform] = suggested
                price_breakdown[platform] = {
                    "ref_platforms": ref_platforms,
                    "avg_price": round(avg_price, 2),
                    "brand_factor": brand_factor,
                    "platform_factor": platform_factor,
                    "final_factor": round(combined_factor, 3),
                    "suggested_price": suggested,
                    "strategy": f"Average price from platforms {ref_platforms} × brand factor ({brand_factor}) × platform factor ({platform_factor})"
                }
            else:
                suggested_prices[platform] = "No Data"
                price_breakdown[platform] = {}

    return {
        "exact_matches": results,
        "similar_products": similar_products,
        "cross_brand_similar_products": similar_products,
        "business_opportunity": suggested_prices,
        "pricing_explanation": price_breakdown,
        "platform_prices_full": {k: v[0] if isinstance(v, list) and v else "Missing" for k, v in results.items() if k in collections},
        "missing_platforms": [platform for platform in collections if results.get(platform) == "Not Available"]
    }

# Normalize and deduplicate values for filter display
def normalize_filter_values(values: List[Any]) -> List[str]:
    """Normalize and deduplicate values for consistent display"""
    # Convert all to strings
    str_values = [str(v) for v in values if v]

    # Use a dictionary to eliminate case duplicates (keeping one preferred version)
    # We'll prefer title case (Apple) over all caps (APPLE) or lowercase (apple)
    case_normalized = {}
    for value in str_values:
        key = value.lower()  # Use lowercase as the key for comparison
        # If we haven't seen this value before or this version is title case, store it
        if key not in case_normalized or value == value.title():
            case_normalized[key] = value

    # Return sorted values
    return sorted(case_normalized.values(), key=lambda x: x.lower())

# Request model
class QueryModel(BaseModel):
    prompt: str

# Chat endpoint using LangChain
@app.post("/ask")
async def ask(query: QueryModel):
    try:
        response = chain.run({"details": query.prompt})
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoint to retrieve chat history
@app.get("/chat_history")
async def get_chat_history():
    return {"chat_history": memory.load_memory_variables({})["chat_history"]}

# Filter retrieval endpoint
@app.get("/get_filters")
async def get_filters(brand: Optional[str] = None, ram: Optional[str] = None, storage: Optional[str] = None):
    query = {}

    # Create case-insensitive queries for all specified filters
    if brand:
        query["Brand"] = {"$regex": f"^{brand.strip()}$", "$options": "i"}
    if ram:
        query["RAM"] = {"$regex": f"^{ram.strip()}$", "$options": "i"}
    if storage:
        query["Storage"] = {"$regex": f"^{storage.strip()}$", "$options": "i"}

    try:
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "brands": {"$addToSet": "$Brand"},
                    "rams": {"$addToSet": "$RAM"},
                    "storages": {"$addToSet": "$Storage"},
                    "processor_types": {"$addToSet": "$Processor Type"},
                    "processor_series": {"$addToSet": "$Processor Series"},
                }
            }
        ]

        result = list(db.reliance.aggregate(pipeline))

        data = {
            "brands": [],
            "rams": [],
            "storages": [],
            "processor_types": [],
            "processor_series": [],
        }

        if result:
            # Apply consistent normalization and sorting to all filter values
            data = {
                "brands": normalize_filter_values(result[0].get("brands", [])),
                "rams": normalize_filter_values(result[0].get("rams", [])),
                "storages": normalize_filter_values(result[0].get("storages", [])),
                "processor_types": normalize_filter_values(result[0].get("processor_types", [])),
                "processor_series": normalize_filter_values(result[0].get("processor_series", [])),
            }

        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

# Product search endpoint
@app.get("/search_products")
async def search_products(
    brand: str = Query(...),
    ram: str = Query(...),
    storage: str = Query(...),
    processor_series: str = Query(...)
):
    try:
        return find_products(brand, ram, storage, processor_series)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching products: {str(e)}")

# GenAI suggestions endpoint
@app.post("/genai_suggestions")
async def genai_suggestions(payload: dict):
    try:
        brand = payload.get("brand")
        ram = payload.get("ram")
        storage = payload.get("storage")
        processor_series = payload.get("processor_series")
        platform_prices = payload.get("platform_prices", {})

        # Fill missing platforms with "Missing"
        for platform in collections:
            if platform not in platform_prices:
                platform_prices[platform] = "Missing"

        result = get_llm_price_suggestion(brand, ram, storage, processor_series, platform_prices)

        structured_response = []
        strategy_notes = ""
        if isinstance(result, str):
            lines = result.strip().split("\n")
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("📌"):
                    parts = line.split("→")
                    if len(parts) >= 2:
                        price_line = f"{parts[0].replace('📌', '').strip()} → ₹{parts[1].strip()}"
                        reason = ""
                        i += 1
                        while i < len(lines) and not lines[i].strip().startswith("📌"):
                            reason += lines[i].strip() + " "
                            i += 1
                        structured_response.append({
                            "platform": parts[0].replace("📌", "").strip(),
                            "price": parts[1].strip().replace("₹", ""),
                            "reason": reason.strip(),
                            "formatted": f"📌 {price_line}\n{reason.strip()}"
                        })
                    else:
                        i += 1
                else:
                    if any(keyword in line.lower() for keyword in ["logic", "strategy", "how", "pricing"]):
                        strategy_notes += line + "\n"
                    i += 1

        return {
            "text": result,
            "structured": structured_response,
            "strategy": strategy_notes.strip()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting GenAI suggestion: {str(e)}")

# Health check
@app.get("/")
async def root():
    return {"message": "LangChain + MongoDB FastAPI running!"}
