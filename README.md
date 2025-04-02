# SPI.AI - Smart Pricing Indicator

## Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/spi-ai.git
cd spi-ai
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Set Up Environment Variables
Create a `.env` file in the project root with:
```
GOOGLE_API_KEY=your_google_api_key_here
```

### 5. Set Up MongoDB Database
```bash
# Start MongoDB service
# On Windows:
net start MongoDB
# On Linux:
sudo systemctl start mongod
```

### 6. Import Data to MongoDB
```bash
mongoimport --db JSONS --collection flipkart --file data/flipkart_json.json --jsonArray
mongoimport --db JSONS --collection croma --file data/croma_json.json --jsonArray
mongoimport --db JSONS --collection reliance --file data/reliance_json.json --jsonArray
mongoimport --db JSONS --collection pai --file data/pai_json.json --jsonArray
```

### 7. Start the Backend Services

#### Start the Main API
```bash
uvicorn backend1:app --reload --port 8000
```

#### Start the Chatbot API
In a new terminal:
```bash
uvicorn chatbot_query:app --reload --port 8001
```

### 8. Launch the Streamlit Frontend
In a new terminal:
```bash
streamlit run trail.py
```

### 9. Access the Application
```
http://localhost:8501
```

## Usage Guide

### Product Search
1. Select a laptop Brand from the dropdown
2. Choose RAM, Storage, and Processor options
3. Click "Search Products" to see pricing across platforms
4. Review the Business Opportunities section for platforms where the product is missing

### ChatBot
Use the sidebar to ask natural language questions such as:
- "What is the price of Dell i5 on Flipkart?"
- "Tell me prices of Dell i7 across platforms"
- "HP Pavilion 16GB RAM i5 price in Croma"

## Troubleshooting

### JSONDecodeError
- Ensure that both backend services (ports 8000 and 8001) are running
- Check server logs for specific error messages

### Case Sensitivity Issues
- The latest version of `backend1.py` handles case-insensitive matching
- If problems persist, check MongoDB collections for data consistency

### No Data Showing
- Verify MongoDB is running with `mongo` command
- Check collections are imported correctly with `use JSONS` then `show collections`
- Ensure the backend APIs are connecting to MongoDB successfully

---

For more detailed documentation, refer to the project specification document.
