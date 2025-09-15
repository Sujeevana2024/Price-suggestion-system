from fastapi import FastAPI, Query
from pymongo import MongoClient
from typing import Dict, List
from genai_utils import get_llm_price_suggestion
from web_utils import search_product_on_web

app = FastAPI()

# Connect to MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["JSONS"]
collections = ["reliance", "pai", "croma", "flipkart"]

# Brand tiers
brand_tiers = {
    "premium": ["apple"],
    "budget": ["avita", "infinix", "jiocloud"],
    "mid": ["acer", "asus", "dell", "hp", "len"]
}

# Platform pricing adjustment
platform_factors = {
    "reliance": 1.00,
    "pai": 0.97,
    "croma": 1.03,
    "flipkart": 0.95
}

def get_brand_tier(brand):
    brand = brand.lower()
    if brand in brand_tiers["premium"]:
        return "premium"
    elif brand in brand_tiers["budget"]:
        return "budget"
    else:
        return "mid"

def find_products(brand, ram, storage, processor_series):
    query = {
        "Brand": {"$regex": f"^{brand.strip()}$", "$options": "i"},
        "RAM": {"$regex": f"^{ram.strip()}$", "$options": "i"},
        "Storage": {"$regex": f"^{storage.strip()}$", "$options": "i"},
    }

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
    found_in_db = False

    for coll in collections:
        exact_match = list(db[coll].find(query, {
            "_id": 0, "Product Name": 1, "Processor Type": 1,
            "Processor Series": 1, "Price": 1, "MRP": 1, "RAM": 1,
            "Storage": 1, "Brand": 1
        }))

        results[coll] = exact_match if exact_match else "Not Available"

        if exact_match:
            found_in_db = True
            prices = [prod["Price"] for prod in exact_match if "Price" in prod]
            platform_prices[coll] = prices
            if prices:
                avg_prices_by_platform[coll] = sum(prices) / len(prices)

        all_products = list(db[coll].find({}, {
            "_id": 0, "Brand": 1, "Product Name": 1, "Processor Type": 1,
            "Processor Series": 1, "Price": 1, "MRP": 1, "RAM": 1, "Storage": 1
        }))

        for product in all_products:
            product_ram = str(product.get("RAM", "")).strip().lower()
            product_storage = str(product.get("Storage", "")).strip().lower()
            product_processor = str(product.get("Processor Series", "")).strip().lower()
            product_brand = str(product.get("Brand", "")).strip().lower()

            if (
                product_ram == ram.strip().lower() and
                product_storage == storage.strip().lower() and
                product_processor == processor_series.strip().lower() and
                product_brand != brand.strip().lower()
            ):
                if coll not in similar_products:
                    similar_products[coll] = []
                similar_products[coll].append(product)

    found_on_web = False
    if not found_in_db:
        query_text = f"{brand} {ram} {storage} {processor_series} laptop"
        found_on_web = search_product_on_web(
            query_text, brand=brand, ram=ram, storage=storage, processor=processor_series
        )

    tier = get_brand_tier(brand)
    brand_factor = {
        "premium": 1.05,
        "mid": 1.00,
        "budget": 0.95
    }[tier]

    suggested_prices = {}
    for platform in collections:
        if not isinstance(results.get(platform), list) or not results.get(platform):
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
                    "strategy": f"Average price from platforms {ref_platforms} × brand factor ({brand_factor}) × platform factor ({platform_factor})",
                    "web_result_found": found_on_web or found_in_db
                }
            else:
                suggested_prices[platform] = "No Data"
                price_breakdown[platform] = {
                    "web_result_found": found_on_web or found_in_db
                }

    return {
        "exact_matches": results,
        "similar_products": similar_products,
        "cross_brand_similar_products": similar_products,
        "business_opportunity": suggested_prices,
        "pricing_explanation": price_breakdown,
        "platform_prices_full": {k: v[0] if isinstance(v, list) and v else "Missing" for k, v in results.items() if k in collections},
        "missing_platforms": [
            platform for platform in collections
            if not isinstance(results.get(platform), list) or not results.get(platform)
        ],
        "web_result_found": found_on_web,
        "found_in_db": found_in_db
    }

@app.get("/get_filters")
async def get_filters(brand: str = None, ram: str = None, storage: str = None):
    query = {}
    if brand:
        query["Brand"] = {"$regex": f"^{brand.strip()}$", "$options": "i"}
    if ram:
        query["RAM"] = {"$regex": f"^{ram.strip()}$", "$options": "i"}
    if storage:
        query["Storage"] = {"$regex": f"^{storage.strip()}$", "$options": "i"}

    pipeline = [
        {"$match": query},
        {"$group": {
            "_id": None,
            "brands": {"$addToSet": "$Brand"},
            "rams": {"$addToSet": "$RAM"},
            "storages": {"$addToSet": "$Storage"},
            "processor_types": {"$addToSet": "$Processor Type"},
            "processor_series": {"$addToSet": "$Processor Series"},
        }}
    ]

    result = list(db.reliance.aggregate(pipeline))
    data = {"brands": [], "rams": [], "storages": [], "processor_types": [], "processor_series": []}
    if result:
        data.update({
            "brands": sorted(result[0].get("brands", [])),
            "rams": sorted(result[0].get("rams", [])),
            "storages": sorted(result[0].get("storages", [])),
            "processor_types": sorted(result[0].get("processor_types", [])),
            "processor_series": sorted(result[0].get("processor_series", [])),
        })
    return data

@app.get("/search_products")
async def search_products(brand: str = Query(...), ram: str = Query(...), storage: str = Query(...), processor_series: str = Query(...)):
    return find_products(brand, ram, storage, processor_series)

@app.post("/genai_suggestions")
async def genai_suggestions(payload: dict):
    brand = payload.get("brand")
    ram = payload.get("ram")
    storage = payload.get("storage")
    processor_series = payload.get("processor_series")
    platform_prices = payload.get("platform_prices")

    platform_prices = {k: v for k, v in platform_prices.items() if v == "Missing"}

    result = get_llm_price_suggestion(brand, ram, storage, processor_series, platform_prices)

    structured_response = []
    strategy_notes = ""
    if isinstance(result, str):
        lines = result.strip().split("\n")
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if line.startswith("📌"):
                parts = line.split("\u2192")
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
