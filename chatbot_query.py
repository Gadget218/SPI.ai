from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pymongo import MongoClient
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.memory import ConversationBufferMemory
from dotenv import load_dotenv
import re
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load environment variables
load_dotenv()

client = MongoClient("mongodb://localhost:27017/")
db = client["JSONS"]
collections = ["reliance", "pai", "croma", "flipkart"]

# LangChain integration
llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro-latest", google_api_key=os.getenv("GOOGLE_API_KEY"))

# FIX: Specify input_key so memory knows which field to store as input
memory = ConversationBufferMemory(memory_key="chat_history", input_key="user_input")

# Enhanced chatbot prompt
chat_prompt = PromptTemplate(
    input_variables=["chat_history", "user_input", "data_results"],
    template="""
    You are a laptop pricing assistant named PriceBot. You provide information about laptop prices across different platforms.

    Chat History:
    {chat_history}

    User Query: {user_input}

    Data from Database:
    {data_results}

    Instructions:
    1. If the database returned results, format them clearly with emojis for better readability.
    2. Include min, max, and average prices for each platform.
    3. If no results were found, suggest the user try different search terms.
    4. Your response should be concise but informative.
    5. Always begin with "🤖 **Hello! I'm PriceBot.**"
    """
)

chain = LLMChain(llm=llm, prompt=chat_prompt, memory=memory)

# Request body schema
class QueryPayload(BaseModel):
    query: str

# Helper to detect platform and keywords
def parse_query_text(query):
    platforms = []
    detected = []
    for name in collections:
        if name in query.lower():
            platforms.append(name)
            detected.append(name)

    if not platforms:
        platforms = collections  # If no platform mentioned, search all

    # Extract key words
    brand_match = re.search(r"\b(apple|asus|dell|hp|acer|avita|infinix|jiocloud|lenovo?)\b", query, re.I)
    processor_match = re.search(r"\b(i3|i5|i7|i9|m1|m2|m3|ryzen ?[3579])\b", query, re.I)
    ram_match = re.search(r"\b(4|8|12|16|32|64) ?gb\b", query, re.I)
    storage_match = re.search(r"\b(128|256|512|1 ?tb|2 ?tb)\b", query, re.I)

    return {
        "platforms": platforms,
        "brand": brand_match.group(0) if brand_match else None,
        "processor": processor_match.group(0) if processor_match else None,
        "ram": ram_match.group(0) if ram_match else None,
        "storage": storage_match.group(0) if storage_match else None
    }

@app.post("/chatbot")
async def chatbot_query(payload: QueryPayload):
    filters = parse_query_text(payload.query)

    if not any([filters["brand"], filters["processor"], filters["ram"], filters["storage"]]):
        return {"response": "❌ **Sorry, I couldn't understand your request. Please ask about a specific laptop model or configuration.**"}

    result = {}

    for coll in filters["platforms"]:
        query = {}
        if filters["brand"]:
            query["Brand"] = {"$regex": filters["brand"], "$options": "i"}
        if filters["ram"]:
            query["RAM"] = {"$regex": filters["ram"].replace(" ", ""), "$options": "i"}
        if filters["storage"]:
            query["Storage"] = {"$regex": filters["storage"].replace(" ", ""), "$options": "i"}
        if filters["processor"]:
            query["$or"] = [
                {"Processor Type": {"$regex": filters["processor"], "$options": "i"}},
                {"Processor Series": {"$regex": filters["processor"], "$options": "i"}}
            ]

        matches = list(db[coll].find(query, {
            "_id": 0,
            "Product Name": 1,
            "Price": 1,
            "MRP": 1
        }))

        if matches:
            result[coll] = matches

    if not result:
        return {"response": "❌ No matching product found. Please rephrase your query."}

    # Generate response using either direct formatting or LangChain
    use_langchain = True  # Toggle this to switch between approaches

    if use_langchain:
        # Format results for LangChain
        query_results_text = []
        for platform, items in result.items():
            price_list = [item["Price"] for item in items if "Price" in item]
            if price_list:
                min_price = min(price_list)
                max_price = max(price_list)
                avg_price = sum(price_list) / len(price_list)
                query_results_text.append(
                    f"{platform.capitalize()}: Min: ₹{min_price}, Avg: ₹{avg_price:.2f}, Max: ₹{max_price}, Number of products: {len(items)}"
                )

        # FIX: Pass the query in user_input field to match memory's input_key
        try:
            response = chain.invoke({
                "user_input": payload.query,
                "data_results": "\n".join(query_results_text)
            })
            return {"response": response["text"]}
        except Exception as e:
            # Fallback to direct formatting if LangChain fails
            print(f"LangChain error: {e}")
            use_langchain = False

    if not use_langchain:
        # Direct formatting approach
        response_lines = ["🤖 **Hello! I'm PriceBot. Here's what I found:**"]
        for platform, items in result.items():
            price_list = [item["Price"] for item in items if "Price" in item]
            if price_list:
                min_price = min(price_list)
                max_price = max(price_list)
                avg_price = sum(price_list) / len(price_list)
                response_lines.append(
                    f"\n📌 **{platform.capitalize()}** → 💰 Min: ₹{min_price}, Avg: ₹{avg_price:.2f}, Max: ₹{max_price}"
                )

        return {"response": "\n".join(response_lines)}

@app.get("/chat_history")
async def get_chat_history():
    return {"chat_history": memory.load_memory_variables({})["chat_history"]}

# Health check
@app.get("/")
async def root():
    return {"message": "PriceBot Query API running!"}
