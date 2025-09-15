import streamlit as st
import requests
import pandas as pd
import base64

st.set_page_config(page_title="Price Suggestion System with Chatbot", layout="wide")

# 🎨 Set background image with dark overlay
def set_background_local(image_file):
    with open(image_file, "rb") as image:
        encoded = base64.b64encode(image.read()).decode()
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/jpg;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background-color: rgba(0, 0, 0, 0.45);
            z-index: -1;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# 🖼️ Set your local image file here
#set_background_local("bg.png")

# 🌐 API endpoints
BASE_URL = "http://127.0.0.1:8002"
CHATBOT_URL = "http://127.0.0.1:8001"

# 💬 Sidebar Chatbot
with st.sidebar:
    st.header("💬 Chat with PriceBot")
    st.markdown("Ask questions like:")
    st.markdown("""
    - What is the price of Dell i5 on Flipkart?
    - Tell me prices of Dell i7 across platforms
    - HP Pavilion 16GB RAM i5 price in Croma
    """)
    user_query = st.text_input("Ask a price-related question:")
    if user_query:
        with st.spinner("Thinking..."):
            try:
                response = requests.post(f"{CHATBOT_URL}/chatbot", json={"query": user_query})
                if response.status_code == 200:
                    result = response.json()
                    st.success(result.get("response", "✅ Response received but no data returned."))
                else:
                    st.error(f"❌ Chatbot backend error: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Chatbot error: {e}")

# 📊 Main UI - SPI.ai Logo & Heading (Enlarged)
st.markdown("""
<div style="display: flex; align-items: center; gap: 0.75rem; margin-top: 10px;">
    <img src="data:image/png;base64,""" + base64.b64encode(open("logo.jpeg", "rb").read()).decode() + """" width="70"/>
    <h1 style="color: white; font-size: 48px; font-weight: 800; margin: 0;">SPI.ai</h1>
</div>
""", unsafe_allow_html=True)

@st.cache_data
def get_filters(brand=None, ram=None, storage=None):
    params = {}
    if brand: params["brand"] = brand
    if ram: params["ram"] = ram
    if storage: params["storage"] = storage
    try:
        response = requests.get(f"{BASE_URL}/get_filters", params=params)
        return response.json()
    except Exception as e:
        st.error(f"❌ Failed to load filters: {e}")
        return {"brands": [], "rams": [], "storages": [], "processor_series": []}

# -- Dropdowns --
filters = get_filters()
brand_options = filters["brands"] + ["Other"]
selected_brand = st.selectbox("Select Brand", brand_options)
brand = st.text_input("Enter Brand") if selected_brand == "Other" else selected_brand

filters = get_filters(brand=brand)
ram_options = filters["rams"] + ["Other"]
selected_ram = st.selectbox("Select RAM", ram_options)
ram = st.text_input("Enter RAM") if selected_ram == "Other" else selected_ram

filters = get_filters(brand=brand, ram=ram)
storage_options = filters["storages"] + ["Other"]
selected_storage = st.selectbox("Select Storage", storage_options)
storage = st.text_input("Enter Storage") if selected_storage == "Other" else selected_storage

filters = get_filters(brand=brand, ram=ram, storage=storage)
processor_options = filters["processor_series"] + ["Other"]
selected_processor = st.selectbox("Select Processor", processor_options)
processor_series = st.text_input("Enter Processor") if selected_processor == "Other" else selected_processor

# -- Submit --
if st.button("Search Products") and processor_series:
    params = {
        "brand": brand,
        "ram": ram,
        "storage": storage,
        "processor_series": processor_series
    }

    with st.spinner("⏳ Searching products and validating online availability..."):
        try:
            response = requests.get(f"{BASE_URL}/search_products", params=params)
            data = response.json()
        except Exception as e:
            st.error(f"❌ Failed to fetch search results: {e}")
            st.stop()

    # -- Display Results --
    st.subheader("📦 Available Products")
    for platform, products in data["exact_matches"].items():
        if isinstance(products, list) and len(products) > 0:
            df = pd.DataFrame(products)
            st.write(f"## {platform.capitalize()}")
            st.dataframe(df)
        else:
            st.write(f"**{platform.capitalize()}** - ❌ Not Available")

    st.subheader("🔍 Similar Products (Other Brands)")
    for platform, products in data.get("cross_brand_similar_products", {}).items():
        if products:
            df_similar = pd.DataFrame(products)
            if not df_similar.empty:
                st.markdown(f"### 📦 {platform.capitalize()}")
                st.dataframe(df_similar, use_container_width=True)
                csv = df_similar.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"⬇️ Download {platform}_similar_products.csv",
                    data=csv,
                    file_name=f"{platform}_similar_products.csv",
                    mime="text/csv"
                )

    # -- Business Opportunity --
    missing_platforms = data.get("missing_platforms", [])
    found_in_db = any(
        isinstance(data["exact_matches"].get(p), list) and len(data["exact_matches"].get(p)) > 0
        for p in ["reliance", "flipkart", "croma", "pai"]
    )
    found_on_web = any(
        explanation.get("web_result_found") is True
        for explanation in data.get("pricing_explanation", {}).values()
    )
    all_web_invalid = not found_in_db and not found_on_web

    if all_web_invalid:
        st.markdown(
            """
            <div style="background-color:#111111;padding:1rem;border-radius:10px;border-left:5px solid red">
                <span style="color:white;font-size:16px;">
                ❌ <strong>This combination seems invalid or doesn't exist online.</strong><br>
                Please check your input.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    elif not missing_platforms:
        st.info("✅ Product is available on all platforms. No business opportunity or GenAI suggestion needed.")
    else:
        st.subheader("💡 Business Opportunities")
        pricing_explanation = data.get("pricing_explanation", {})
        for platform, price in data["business_opportunity"].items():
            explanation = pricing_explanation.get(platform, {})
            if isinstance(price, (int, float)):
                st.markdown(
                    f"""
                    <div style='background-color: #111; color: white; padding: 1rem; border-radius: 10px; margin-bottom: 0.75rem;'>
                    🔗 <strong>{platform.capitalize()}</strong> → Suggested Price: ₹{price}
                    </div>
                    """,
                    unsafe_allow_html=True
                )
            elif explanation.get("web_result_found") is True:
                st.info(f"🔗 **{platform.capitalize()}** → ✅ This product exists online, but we have no pricing data.")

        with st.expander("📘 How Business Opportunity Prices are Calculated"):
            st.markdown("""
            We calculate suggested prices for platforms where the product is **not available**.

            Formula used:
            ```
            suggested_price = average_price × brand_factor × platform_factor
            ```
            - **Brand Factor:**
                - Premium: 1.05
                - Mid: 1.00
                - Budget: 0.95
            - **Platform Factor:**
                - Croma: 1.10
                - Flipkart: 1.05
                - Pai: 1.03
                - Reliance: 1.00
            """)

        full_platform_prices = {platform: "Missing" for platform in missing_platforms}
        genai_payload = {
            "brand": brand,
            "ram": ram,
            "storage": storage,
            "processor_series": processor_series,
            "platform_prices": full_platform_prices
        }

        try:
            with st.spinner("🤖 Thinking... Generating suggestions using GenAI..."):
                genai_response = requests.post(f"{BASE_URL}/genai_suggestions", json=genai_payload).json()

            st.subheader("🤖 GenAI Price Suggestion")
            if "structured" in genai_response and genai_response["structured"]:
                for entry in genai_response["structured"]:
                    if entry["platform"].lower() in missing_platforms:
                        with st.container():
                            st.markdown(f"### 🔗 {entry['platform'].capitalize()}")
                            st.markdown(f"💰 **Suggested Price:** ₹{entry['price']}")
                            if entry.get("reason"):
                                st.markdown("📝 **Why this price?**")
                                st.markdown(
                                    f"""
                                    <div style="
                                        background-color: #111;
                                        border-left: 5px solid #ff4b4b;
                                        color: white;
                                        padding: 1rem;
                                        margin-top: 0.5rem;
                                        border-radius: 10px;
                                        box-shadow: 0 4px 10px rgba(255,255,255,0.1);
                                        font-size: 16px;
                                    ">
                                    <strong>Reason:</strong> {entry['reason']}
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                            else:
                                st.warning("⚠️ No reasoning was provided by the model.")
            else:
                st.warning("⚠️ GenAI Error: No response.")
        except Exception as e:
            st.error(f"❌ GenAI call failed: {e}")
