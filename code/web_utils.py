import re
import os
from serpapi import GoogleSearch
from dotenv import load_dotenv

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")

def normalize(text):
    return re.sub(r"[^a-zA-Z0-9 ]", "", text).lower().strip()

def search_product_on_web(query, num_results=5, brand=None, ram=None, storage=None, processor=None):
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not found in environment variables")

    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num_results
    }

    try:
        search = GoogleSearch(params)
        results = search.get_dict().get("organic_results", [])

        # Normalize target inputs
        norm_brand = normalize(brand or "")
        norm_ram = normalize(ram or "").replace("gb", "")
        norm_storage = normalize(storage or "").replace("gb", "").replace("tb", "")
        norm_proc = normalize(processor or "")

        for result in results:
            text = normalize(result.get("title", "") + " " + result.get("snippet", ""))
            if (norm_brand in text and
                (norm_ram in text or ram in text) and
                (norm_storage in text or storage in text) and
                norm_proc in text):
                return True
        return False
    except Exception as e:
        print("❌ Web search failed:", e)
        return False
