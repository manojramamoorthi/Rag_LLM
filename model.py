from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate
import google.generativeai as genai
import argparse
from dotenv import load_dotenv
import os

PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Extract and summarize the Answer from the above context 
You should not use any information out of the knowledge of the context.
If the question is unrelated to the context politely decline
Give a detailed explaination
Question: {question}
"""

def main():
    # Create CLI.
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    query_text = args.query_text
    print(query_rag(query_text))

def get_embedding_function():
    embeddings = OllamaEmbeddings(model="mxbai-embed-large:335m")
    return embeddings

def query_rag(query_text: str):
    # Prepare the DB.
    embedding_function = get_embedding_function()
    db = Chroma(persist_directory="Database", embedding_function=embedding_function)

    # Search the DB.
    print("Searching...")
    results = db.similarity_search_with_score(query_text, k=10)
    print("Search Finished")

    context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
    prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
    prompt = prompt_template.format(context=context_text, question=query_text)
    #print(context_text)
    
    load_dotenv()
    genai.configure(api_key=os.getenv('google_api'))

    
    #print("Model Generation")
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)

    #sources = [doc.metadata.get("id", None) for doc, _score in results]
    #formatted_response = f"Response: {response.text}\nSources: {sources}"
    print("response complete")
    return response.text

if __name__ == "__main__":
    main()