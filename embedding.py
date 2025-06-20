from langchain_ollama import OllamaEmbeddings


def get_embedding_function():
    embeddings = OllamaEmbeddings(model="mxbai-embed-large:335m")
    return embeddings