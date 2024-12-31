import os
from flask import Flask, render_template, request, jsonify
from better_profanity import profanity
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
import random
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

os.environ["GOOGLE_API_KEY"] = "AIzaSyDJx7I5gVLTGIuB4FZnzP-A1qrt_YeKVlo"
embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

persist_dir = "memory_store"
vector_store = None

class CustomEmbeddingWrapper:
    def __init__(self, base_embedding):
        self.base_embedding = base_embedding

    def embed_documents(self, texts):
        return [self.base_embedding.embed_query(text) for text in texts]

    def embed_query(self, text):
        return self.base_embedding.embed_query(text)

def initialize_memory_store():
    global vector_store
    try:
        embedding_wrapper = CustomEmbeddingWrapper(embedding_model)
        vector_store = Chroma(
            persist_directory=persist_dir,
            embedding_function=embedding_wrapper
        )
        print("Initialized persistent memory store.")
    except Exception as e:
        print(f"Error initializing memory store: {e}")
        raise

def add_scraped_data_to_memory(data):
    try:
        if vector_store is None:
            initialize_memory_store()

        documents = [
            Document(
                page_content=item["description"],
                metadata={"title": item["title"], "price": item["price"]}
            )
            for item in data
        ]
        vector_store.add_documents(documents)
        print(f"Added {len(data)} items to memory store.")

    except Exception as e:
        print(f"Error adding scraped data to memory: {e}")

@app.route("/scrape", methods=["GET"])
def scrape_data():
    url = "https://hydrobit.store/"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        scraped_data = []
        products = soup.find_all("div", class_="product-item")

        for product in products:
            title = product.find("h2").text.strip()
            description = product.find("p", class_="description").text.strip()
            price = product.find("span", class_="price").text.strip()

            scraped_data.append({
                "title": title,
                "description": description,
                "price": price
            })

        if not scraped_data:
            print("No products found during scraping.")
            return jsonify({"error": "No products found."})

        add_scraped_data_to_memory(scraped_data)
        print(f"Scraped Data: {scraped_data}")  # Log scraped data
        return jsonify({"message": "Data scraped and added to memory!", "data": scraped_data})

    except Exception as e:
        print(f"Scraping error: {e}")
        return jsonify({"error": "Failed to scrape data."})

def generate_response(user_message: str):
    try:
        if vector_store is None:
            initialize_memory_store()

        query_embedding = embedding_model.embed_query(user_message)
        similar_entries = vector_store.similarity_search_by_vector(query_embedding, k=3)

        print(f"Similar Entries: {similar_entries}")  # Debugging

        context = ""
        if similar_entries:
            context = " ".join([entry.page_content for entry in similar_entries])

        llm_prompt = f"""
        Context from memory: {context}
        User: {user_message}
        Assistant:"""
        
        google_llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0.7)
        llm_response = google_llm.predict(llm_prompt)
        return llm_response

    except Exception as e:
        print(f"Error generating response: {e}")
        return "I'm having trouble processing your request."

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/get_response", methods=["POST"])
def get_response():
    try:
        user_message = request.json.get("message")

        if not user_message:
            return jsonify({"response": "Please provide a valid question."})

        response = generate_response(user_message)
        return jsonify({"response": response})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"response": "An error occurred while processing your request."})

if __name__ == "__main__":
    try:
        initialize_memory_store()
        app.run(debug=True)
    except Exception as e:
        print(f"Startup error: {e}")
