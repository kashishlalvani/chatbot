import os
from flask import Flask, render_template, request, jsonify
from langchain_google_genai import GoogleGenerativeAIEmbeddings, ChatGoogleGenerativeAI
from langchain_community.vectorstores import Chroma
# from langchain_chroma import Chroma
from langchain_core.documents import Document
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# from better_profanity import profanity
# import random

load_dotenv()

app = Flask(__name__)
google_api_key = os.getenv("GOOGLE_API_KEY")
os.environ["GOOGLE_API_KEY"] = google_api_key
embedding_model = GoogleGenerativeAIEmbeddings(model="models/embedding-001")

PERSIST_DIR = "memory_store"
VECTOR_STORE = None

class CustomEmbeddingWrapper:
    def __init__(self, base_embedding):
        self.base_embedding = base_embedding

    def embed_documents(self, texts):
        return [self.base_embedding.embed_query(text) for text in texts]

    def embed_query(self, text):
        return self.base_embedding.embed_query(text)

def initialize_memory_store():
    global VECTOR_STORE
    try:
        embedding_wrapper = CustomEmbeddingWrapper(embedding_model)
        VECTOR_STORE = Chroma(
            persist_directory=PERSIST_DIR,
            embedding_function=embedding_wrapper
        )
        print("Initialized persistent memory store.")
    except Exception as e:
        print(f"Error initializing memory store: {e}")
        raise

def add_scraped_data_to_memory(data):
    try:
        if VECTOR_STORE is None:
            initialize_memory_store()

        documents = [
            Document(
                page_content=item["content"],
                metadata={"title": item["type"]}
            )
            for item in data
        ]
        VECTOR_STORE.add_documents(documents)
        print(f"Added {len(documents)} items to memory store.")

    except Exception as e:
        print(f"Error adding scraped data to memory: {e}")


def scrap_data_with_selenium():
    url = "https://hydrobit.store"
    
    options = Options()
    options.headless = True
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        driver.implicitly_wait(15)

        # Extract the main heading (heroContent)
        main_heading_elements = driver.find_elements(By.CLASS_NAME, "heroContent")
        print(f"Main headings found: {len(main_heading_elements)}")  # Debugging
        main_headings = [heading.text.strip() for heading in main_heading_elements]

        # Extract the additional title (overflow-x-hidden)
        additional_titles_elements = driver.find_elements(By.CLASS_NAME, "overflow-x-hidden")
        print(f"Additional titles found: {len(additional_titles_elements)}")  # Debugging
        additional_titles = [title.text.strip() for title in additional_titles_elements]

        # Extract the features (component-description)
        feature_elements = driver.find_elements(By.CSS_SELECTOR, "h2.component-description")
        print(f"Feature elements found: {len(feature_elements)}")  # Debugging
        features = [feature.text.strip() for feature in feature_elements]

        # Now, we'll organize them in separate entries as you want.
        scraped_data = []

        # Add main headings to scraped data (Titles)
        for heading in main_headings:
            scraped_data.append({
                "type": "Main Heading",
                "content": heading
            })

        # Add additional titles to scraped data (Titles)
        for additional_title in additional_titles:
            scraped_data.append({
                "type": "Additional Title",
                "content": additional_title
            })

        # Add features to scraped data (Features)
        for feature in features:
            if feature:  # Avoid adding empty features
                scraped_data.append({
                    "type": "Feature",
                    "content": feature
                })

        # Add scraped data to memory store (ChromaDB)
        add_scraped_data_to_memory(scraped_data)

        return scraped_data

    except Exception as e:
        print(f"Error during Selenium scraping: {e}")
        return []

    finally:
        driver.quit()





def generate_response(user_message: str):
    try:
        if VECTOR_STORE is None:
            initialize_memory_store()
        if "hydrobit.store" in user_message:
            return "I can help you with information about products from hydrobit.store. What would you like to know?"

        try:
            query_embedding = embedding_model.embed_query(user_message)
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return "There was an issue with generating the embedding."

        similar_entries = VECTOR_STORE.similarity_search_by_vector(query_embedding, k=3)

        print(f"Similar Entries: {similar_entries}")  # Debugging

        context = ""
        if similar_entries:
            context = " ".join([entry.page_content for entry in similar_entries])

        llm_prompt = f"""
        Context from memory: {context}
        User: {user_message}
        Assistant:  """
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
        return jsonify({"response": f"An error occurred: {str(e)}"})
    
@app.route("/scrape", methods=["GET"])
def scrape():
    try:
        scraped_data = scrap_data_with_selenium()  # Get both titles and features
        if not scraped_data:
            return jsonify({"message": "No data was scraped.", "scraped_data": []})

        # Add scraped data to memory store
        add_scraped_data_to_memory(scraped_data)
        print()

        return jsonify({
            "message": f"Scraped {len(scraped_data)} items successfully!",
            "scraped_data": scraped_data
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"response": f"An error occurred while scraping: {str(e)}"})


if __name__ == "__main__":
    try:
        initialize_memory_store()
        app.run(debug=True)
    except Exception as e:
        print(f"Startup error: {e}")

