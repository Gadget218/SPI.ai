from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
import os
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure Google GenAI API directly
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
direct_model = genai.GenerativeModel("models/gemini-1.5-pro-latest")

# LangChain approach for response generation
def generate_response_langchain(prompt):
    llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", google_api_key=os.getenv("GOOGLE_API_KEY"))
    template = """
    You are a pricing assistant. Given the following details:
    {details}
    Provide a concise and clear price suggestion.
    """
    prompt_template = PromptTemplate(template=template, input_variables=["details"])
    chain = LLMChain(llm=llm, prompt=prompt_template)
    return chain.run({"details": prompt})

# Direct Google GenAI approach for price suggestions
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

📌 Flipkart → ₹57,000 (this is an example, you should suggest your own price similar to the platform_prices)
Reason: Based on average pricing of similar products and brand positioning...

📌 Croma → ₹59,000 (this is an example, you should suggest your own price similar to the platform_prices)
Reason: Higher due to premium platform and product visibility...

⚠️ Do not skip the 'Reason' part.
"""

    try:
        response = direct_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("🔥 GenAI Error:", e)
        return f"⚠️ GenAI Error: {e}"

# Example usage
if __name__ == "__main__":
    # Test LangChain approach
    prompt = "Laptop with 16GB RAM, 1TB SSD, and i7 processor."
    print("LangChain Response:", generate_response_langchain(prompt))

    # Test direct GenAI approach
    test_platform_prices = {
        "reliance": 75000,
        "pai": "Missing",
        "croma": 78000,
        "flipkart": "Missing"
    }
    print("GenAI Direct Response:", get_llm_price_suggestion("Dell", "16GB", "1TB", "i7", test_platform_prices))
