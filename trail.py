import streamlit as st
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
import requests
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("Missing Google API Key. Set it in your environment variables!")

# Backend URLs
BASE_URL = "http://127.0.0.1:8000"
CHATBOT_URL = "http://127.0.0.1:8001"

st.set_page_config(page_title="Price Suggestion System with LangChain", layout="wide")

# ✅ Use Gemini API through LangChain
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro-latest",
    google_api_key=GOOGLE_API_KEY
)

memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Chatbot
chat_prompt = PromptTemplate(
    input_variables=["chat_history", "user_input"],
    template="""
    You are a pricing assistant that suggests competitive prices for laptops based on the given configurations.
    {chat_history}

    User: {user_input}
    """
)
chat_chain = LLMChain(llm=llm, memory=memory, prompt=chat_prompt)

# Sidebar Chatbot
with st.sidebar:
    st.header("💬 Chat with PriceBot")
    st.markdown("Ask price-related questions like:")
    st.markdown("""
    - What is the price of Dell i5 on Flipkart?
    - Tell me prices of Dell i7 across platforms
    - HP Pavilion 16GB RAM i5 price in Croma
    """)

    user_query = st.text_input("Ask a price-related question:")

    if user_query:
        # Use either the LangChain approach or call the chatbot API
        use_api = True  # Toggle this based on your preference

        with st.spinner("Thinking..."):
            if use_api:
                # Use the chatbot API from chatbot_query.py
                try:
                    response = requests.post(f"{CHATBOT_URL}/chatbot", json={"query": user_query})

                    # Enhanced error handling
                    if response.status_code == 200:
                        data = response.json()
                        st.success(data.get("response", "No response from chatbot."))
                    else:
                        st.error(f"Server error: {response.status_code}")
                        st.error(f"Response: {response.text[:500]}...")  # Show first 500 chars of error
                except Exception as e:
                    st.error(f"Error connecting to chatbot service: {str(e)}")
                    st.info("Using fallback LangChain directly...")
                    # Fallback to direct LangChain if server fails
                    try:
                        response = chat_chain.run(user_input=user_query)
                        st.success(response)
                    except Exception as inner_e:
                        st.error(f"LangChain error: {str(inner_e)}")
            else:
                # Use LangChain directly
                try:
                    response = chat_chain.run(user_input=user_query)
                    st.success(response)
                except Exception as e:
                    st.error(f"LangChain error: {str(e)}")

# Main UI
st.title("📊 Price Suggestion System")

# Fetch filters dynamically
def get_filters(brand=None, ram=None, storage=None):
    """Fetch filters dynamically based on selection."""
    try:
        params = {}
        if brand:
            params["brand"] = brand
        if ram:
            params["ram"] = ram
        if storage:
            params["storage"] = storage

        response = requests.get(f"{BASE_URL}/get_filters", params=params)
        if response.status_code != 200:
            st.error(f"Error from server: {response.status_code}")
            return {"brands": [], "rams": [], "storages": [], "processor_series": []}

        data = response.json()
        return data
    except Exception as e:
        st.error(f"Error fetching filters: {e}")
        return {"brands": [], "rams": [], "storages": [], "processor_series": []}

# Initial filter fetch
filters = get_filters()

# Error handling for empty dropdowns
if not filters.get("brands"):
    st.error("⚠️ No data retrieved from database. Make sure MongoDB is running and has data.")
    st.stop()

# Brand selection with empty option as first choice
brand_options = [""] + filters.get("brands", [])
brand = st.selectbox("Select Brand", brand_options, index=0)

# Only proceed if brand is selected
if brand:
    # Update filters based on brand
    ram_filters = get_filters(brand=brand)
    ram_options = [""] + ram_filters.get("rams", [])
    ram = st.selectbox("Select RAM", ram_options, index=0)

    # Only proceed if RAM is selected
    if ram:
        # Update filters based on brand and RAM
        storage_filters = get_filters(brand=brand, ram=ram)
        storage_options = [""] + storage_filters.get("storages", [])
        storage = st.selectbox("Select Storage", storage_options, index=0)

        # Only proceed if storage is selected
        if storage:
            # Final filter update for processor
            processor_filters = get_filters(brand=brand, ram=ram, storage=storage)
            processor_options = processor_filters.get("processor_series", [])

            if processor_options:
                processor_series = st.selectbox("Select Processor", processor_options)
            else:
                st.warning("No processors available for the selected configuration.")
                processor_series = None
        else:
            st.info("Please select storage")
            processor_series = None
    else:
        st.info("Please select RAM")
        storage = None
        processor_series = None
else:
    st.info("Please select a brand to continue")
    ram = None
    storage = None
    processor_series = None

# Product Search
if st.button("Search Products"):
    if brand and ram and storage and processor_series:
        with st.spinner("Searching products..."):
            params = {
                "brand": brand,
                "ram": ram,
                "storage": storage,
                "processor_series": processor_series
            }
            try:
                response = requests.get(f"{BASE_URL}/search_products", params=params)
                if response.status_code != 200:
                    st.error(f"Error from server: {response.status_code}")
                    st.error(f"Details: {response.text[:500]}...")  # Show first 500 chars of error
                    st.stop()

                data = response.json()

                # Display Products
                st.subheader("🛒 Available Products")
                for platform, products in data["exact_matches"].items():
                    if isinstance(products, list) and products:
                        df = pd.DataFrame(products)
                        min_price = df["Price"].min()
                        max_price = df["Price"].max()
                        avg_price = df["Price"].mean()
                        most_common_price = df["Price"].mode().values[0] if not df["Price"].mode().empty else avg_price
                        competitive_price = round(avg_price * 0.95, 2)
                        premium_price = round(avg_price * 1.10, 2)

                        st.write(f"## {platform.capitalize()}")
                        st.markdown(f"🏷️ **Min Price:** ₹{min_price} | 💰 **Avg Price:** ₹{avg_price:.2f} | 🏆 **Max Price:** ₹{max_price}")
                        st.markdown(f"1️⃣ **Lowest Competitor:** ₹{min_price} | 2️⃣ **Most Common Price:** ₹{most_common_price} | 3️⃣ **Highest Competitor:** ₹{max_price}")
                        st.markdown(f"🔹 **Competitive:** ₹{competitive_price} | 🔹 **Market:** ₹{avg_price:.2f} | 🔹 **Premium:** ₹{premium_price}")
                    else:
                        st.write(f"**{platform.capitalize()}** - ❌ Not Available")

                # Display Similar Products
                st.subheader("🔍 Similar Products")
                for platform, products in data["cross_brand_similar_products"].items():
                    if products:
                        st.write(f"**{platform.capitalize()}**")
                        st.dataframe(pd.DataFrame(products))

                # Display Business Opportunities
                st.subheader("💡 Business Opportunities")
                for platform, price in data["business_opportunity"].items():
                    st.write(f"📌 **{platform.capitalize()}** → Suggested Price: ₹{price}")

                # GenAI Suggestions
                with st.expander("📘 How Business Opportunity Prices are Calculated"):
                    st.markdown("""
                    We calculate suggested prices for platforms where the product is **not available**.

                    Formula used:
                    ```suggested_price = average_price × brand_factor × platform_factor```

                    - **Brand Factor:**
                        - Premium: 1.05
                        - Mid: 1.00
                        - Budget: 0.95
                    - **Platform Factor:**
                        - Croma: 1.10
                        - Flipkart: 1.05
                        - Pai: 1.03
                        - Reliance: 1.00

                    This keeps pricing realistic and competitive.
                    """)

                # Generate AI suggestions for missing platforms
                all_platforms = ["reliance", "flipkart", "croma", "pai"]
                missing_platforms = [
                    platform for platform in all_platforms
                    if not (isinstance(data["exact_matches"].get(platform), list) and data["exact_matches"].get(platform))
                ]

                if missing_platforms:
                    full_platform_prices = {
                        platform: (
                            data["exact_matches"].get(platform, [{}])[0].get("Price")
                            if isinstance(data["exact_matches"].get(platform), list) and data["exact_matches"].get(platform) else None
                        )
                        for platform in all_platforms
                    }

                    genai_payload = {
                        "brand": brand,
                        "ram": ram,
                        "storage": storage,
                        "processor_series": processor_series,
                        "platform_prices": full_platform_prices
                    }

                    try:
                        genai_response = requests.post(f"{BASE_URL}/genai_suggestions", json=genai_payload)

                        if genai_response.status_code != 200:
                            st.error(f"Error from GenAI service: {genai_response.status_code}")
                            st.error(f"Details: {genai_response.text[:500]}...")
                        else:
                            genai_data = genai_response.json()

                            st.subheader("🤖 GenAI Price Suggestion")
                            if "structured" in genai_data and genai_data["structured"]:
                                for entry in genai_data["structured"]:
                                    if entry["platform"].lower() in missing_platforms:
                                        with st.container():
                                            st.markdown(f"### 📌 {entry['platform'].capitalize()}")
                                            st.markdown(f"💰 **Suggested Price:** ₹{entry['price']}")
                                            if entry.get("reason"):
                                                st.markdown("📝 **Why this price?**")
                                                st.info(entry["reason"])
                                            else:
                                                st.warning("⚠️ No reasoning was provided by the model.")
                            else:
                                st.warning("⚠️ GenAI Error: No structured response.")
                                st.info(f"Raw response: {genai_data.get('text', 'No text available')[:500]}...")

                    except Exception as e:
                        st.error(f"Error getting GenAI suggestions: {str(e)}")
                else:
                    st.info("✅ Product is already available on all platforms. No GenAI suggestions needed.")

            except Exception as e:
                st.error(f"Error searching products: {e}")
    else:
        st.warning("Please select all filter options before searching.")
