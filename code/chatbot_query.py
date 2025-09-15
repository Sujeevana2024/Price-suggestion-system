from fastapi import FastAPI, Request
from pymongo import MongoClient
from genai_utils import get_llm_price_suggestion
from web_utils import search_product_on_web
import pandas as pd

app = FastAPI()

client = MongoClient("mongodb://localhost:27017/")
db = client["JSONS"]
collections = ["reliance", "pai", "croma", "flipkart"]

def normalize_ram(ram):
    if not ram:
        return ""
    return str(ram).lower().replace(" ", "")

def normalize_storage(storage):
    if not storage:
        return ""
    return str(storage).lower().replace(" ", "")

def normalize_processor(proc):
    if not proc:
        return ""
    proc = proc.lower().replace(" ", "")
    mapping = {
        "i3": "i3", "corei3": "i3",
        "i5": "i5", "corei5": "i5",
        "i7": "i7", "corei7": "i7",
        "i9": "i9", "corei9": "i9",
        "ryzen5": "ryzen5", "ryzen7": "ryzen7"
    }
    return mapping.get(proc, proc)

def extract_components(query):
    query = query.lower()
    brand = next((b for b in ["dell", "hp", "asus", "acer", "apple"] if b in query), None)
    ram = normalize_ram(next((r for r in ["8gb", "16gb", "32gb", "64gb"] if r in query.replace(" ", "")), None))
    storage = normalize_storage(next((s for s in ["256gb", "512gb", "1tb", "2tb"] if s in query.replace(" ", "")), None))
    processor = normalize_processor(next((p for p in ["i3", "i5", "i7", "i9", "ryzen5", "ryzen7"] if p in query.replace(" ", "")), None))
    platform = next((p for p in collections if p in query), None)
    return brand, ram, storage, processor, platform

def get_price_from_db(brand, ram, storage, processor, platform=None):
    results = []
    search_collections = [platform] if platform else collections

    for coll in search_collections:
        docs = db[coll].find({}, {
            "Product Name": 1,
            "Price": 1,
            "RAM": 1,
            "Storage": 1,
            "Processor Series": 1,
            "Processor Type": 1,
            "Brand": 1,
            "_id": 0
        })

        for doc in docs:
            match = True

            if brand and brand.lower() not in str(doc.get("Brand", "")).lower():
                match = False
            if platform and coll != platform:
                match = False
            if ram and ram != normalize_ram(doc.get("RAM", "")):
                match = False
            if storage and storage != normalize_storage(doc.get("Storage", "")):
                match = False
            if processor:
                processor_info = f"{doc.get('Processor Series', '')} {doc.get('Processor Type', '')}"
                if processor not in normalize_processor(processor_info):
                    match = False

            if match:
                results.append({
                    "platform": coll,
                    "product": doc.get("Product Name"),
                    "price": doc.get("Price"),
                    "ram": doc.get("RAM"),
                    "storage": doc.get("Storage"),
                    "processor": doc.get("Processor Series")
                })

    return results

@app.post("/chatbot")
async def chatbot(request: Request):
    data = await request.json()
    query = data.get("query", "").strip()
    if not query:
        return {"response": "⚠️ Please enter a valid query."}

    brand, ram, storage, processor, platform = extract_components(query)
    db_results = get_price_from_db(brand, ram, storage, processor, platform)

    if db_results:
        df = pd.DataFrame(db_results)
        grouped = df.groupby("platform")
        response_lines = ["✅ Product found in our database:\n"]
        for platform, group in grouped:
            response_lines.append(f"🔸 **{platform.capitalize()}**")
            for _, row in group.iterrows():
                response_lines.append(
                    f"• **Product:** {row['product']}\n"
                    f"  → ₹{row['price']}\n"
                    f"  RAM: {row['ram']} | Storage: {row['storage']} | Processor: {row['processor']}\n"
                )
        return {"response": "\n".join(response_lines)}

    if brand or processor or ram or storage:
        search_text = f"{brand or ''} {ram or ''} {storage or ''} {processor or ''} laptop"
        web_results = search_product_on_web(search_text)
        if isinstance(web_results, list) and len(web_results) > 0:
            response_lines = ["🌐 Product not in our DB. Found using web search:\n"]
            for res in web_results[:3]:
                title = res.get("title", "").strip()
                link = res.get("link", "")
                snippet = res.get("snippet", "")
                response_lines.append(f"🔗 **{title}**\n{snippet}\n{link}\n")
            return {"response": "\n".join(response_lines)}

        return {"response": "❌ No matching product found in web search either."}

    return {"response": "❌ No matching product found. Please rephrase your query."}
