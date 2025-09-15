import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# ✅ Corrected environment variable usage
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# ✅ Use a model that works with the public API
model = genai.GenerativeModel("models/gemini-1.5-pro-latest")


def get_llm_price_suggestion(brand, ram, storage, processor, platform_prices):
    prompt = f"""
You are a pricing assistant AI.

A vendor wants to list the following product:
Brand: {brand}
RAM: {ram}
Storage: {storage}
Processor: {processor}

Here are the prices of the same/similar product on other platforms:
{chr(10).join([f"{k.capitalize()}: ₹{v}" for k, v in platform_prices.items()])}

Some platforms are missing this product.

✅ Your task:
- Suggest a selling price for each **missing** platform.
- For **each price**, explain clearly why you recommended that amount.
- Consider market trends, brand tier, pricing patterns, and platform factors.
- Always write in this format:

📌 Flipkart → ₹57,000(Don't use exact number as in the example , use the platform prices and consider and all products specs and give the pricing and resoning in accordance to it.)  
Reason: Based on average pricing of similar products and brand positioning...

📌 Croma → ₹59,000 (Don't use exact number as in the example , use the platform prices and consider and all products specs and give the pricing and resoning in accordance to it.)
Reason: Higher due to premium platform and product visibility...

⚠️ Do not skip the 'Reason' part.
"""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("🔥 GenAI Error:", e)
        return f"⚠️ GenAI Error: {e}"
