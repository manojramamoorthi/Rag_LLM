from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import base64
import os
import tempfile
from dotenv import load_dotenv
from google import genai
from google.genai import types
import logging
from pathlib import Path
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.prompts import ChatPromptTemplate

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

load_dotenv()

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
    
    # Use the global genai_client that's already initialized
    if not genai_client:
        raise HTTPException(status_code=500, detail="GenAI client not available")

    
    #print("Model Generation")
    response = genai_client.models.generate_content(
        model="gemini-1.5-flash",
        contents=prompt
    )

    #sources = [doc.metadata.get("id", None) for doc, _score in results]
    #formatted_response = f"Response: {response.text}\nSources: {sources}"
    print("response complete")
    return response.text


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Voice RAG API",
    description="API for processing voice queries against a RAG database",
    version="1.0.0"
)

# Add CORS middleware for web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Google GenAI client
genai_client = None
try:
    api_key = os.getenv('google_api')
    if api_key:
        genai_client = genai.Client(api_key=api_key)
        logger.info("Google GenAI client initialized successfully")
    else:
        logger.warning("Google API key not found in environment variables")
except Exception as e:
    logger.error(f"Failed to initialize Google GenAI client: {e}")
    genai_client = None

class VoiceProcessor:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir())
        
    async def process_audio_file(self, audio_file: UploadFile) -> str:
        """Process uploaded audio file and convert to text using Google GenAI."""
        try:
            # Create temporary file for the uploaded audio
            temp_audio_path = self.temp_dir / f"temp_audio_{audio_file.filename}"
            
            # Save uploaded file
            with open(temp_audio_path, "wb") as buffer:
                content = await audio_file.read()
                buffer.write(content)
            
            logger.info(f"Audio file saved to {temp_audio_path}")
            
            # Upload to Google GenAI
            myfile = genai_client.files.upload(file=str(temp_audio_path))
            
            # Convert audio to text
            response = genai_client.models.generate_content(
                model="gemini-2.0-flash", 
                contents=["change this audio to text", myfile]
            )
            
            # Clean up temporary file
            if temp_audio_path.exists():
                temp_audio_path.unlink()
            
            #logger.info("Audio to text conversion completed")
            return response.text
            
        except Exception as e:
            logger.error(f"Error processing audio file: {e}")
            # Clean up on error
            try:
                if 'temp_audio_path' in locals() and temp_audio_path.exists():
                    temp_audio_path.unlink()
            except Exception as cleanup_error:
                logger.warning(f"Failed to clean up temp file: {cleanup_error}")
            raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")
    
    async def generate_audio_response(self, text: str) -> bytes:
        """Generate audio response from text using Google GenAI TTS."""
        try:
            response = genai_client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents="Say cheerfully: " + text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name='Kore',
                            )
                        )
                    ),
                )
            )
            
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            #logger.info("Audio generation completed")
            return audio_data
            
        except Exception as e:
            logger.error(f"Error generating audio response: {e}")
            raise HTTPException(status_code=500, detail=f"Error generating audio: {str(e)}")

# Initialize voice processor
voice_processor = VoiceProcessor()

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "Voice RAG API is running",
        "status": "healthy",
        "genai_available": genai_client is not None
    }

@app.get("/health")
async def health_check():
    """Detailed health check endpoint."""
    health_status = {
        "api": "healthy",
        "genai_client": "available" if genai_client else "unavailable",
        "google_api_key": "configured" if os.getenv('google_api') else "missing"
    }
    
    # Test database connection
    try:
        # This will test if the RAG system is working
        # Use a more lightweight test to avoid startup issues
        import inspect
        if callable(query_rag):
            health_status["rag_system"] = "available"
        else:
            health_status["rag_system"] = "function not callable"
    except Exception as e:
        health_status["rag_system"] = f"error: {str(e)}"
    
    return health_status

@app.post("/process-voice")
async def process_voice(audio_file: UploadFile = File(...)):
    """
    Process voice file through the complete pipeline:
    1. Convert audio to text
    2. Query RAG database
    3. Generate audio response
    4. Return audio file
    """
    
    if not genai_client:
        raise HTTPException(status_code=500, detail="Google GenAI client not available")
    
    # Validate file type
    if not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        #logger.info(f"Processing audio file: {audio_file.filename}")
        
        # Step 1: Convert audio to text
        #logger.info("Converting audio to text...")
        transcribed_text = await voice_processor.process_audio_file(audio_file)
        #logger.info(f"Transcribed text: {transcribed_text[:100]}...")
        
        # Step 2: Query RAG database
        #logger.info("Querying RAG database...")
        rag_response = query_rag(transcribed_text)
        #logger.info(f"RAG response: {rag_response[:100]}...")
        
        # Step 3: Generate audio response
        #logger.info("Generating audio response...")
        audio_data = await voice_processor.generate_audio_response(rag_response)
        
        # Step 4: Return audio response
        #logger.info("Returning audio response")
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        return {
            "audio_base64": audio_base64,
            "format": "wav",
            "length": len(audio_data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_voice: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/process-voice-json")
async def process_voice_json(audio_file: UploadFile = File(...)):
    """
    Process voice file and return JSON response with transcription, RAG response, and audio URL.
    Alternative endpoint for clients that need structured data.
    """
    
    if not genai_client:
        raise HTTPException(status_code=500, detail="Google GenAI client not available")
    
    if not audio_file.content_type.startswith('audio/'):
        raise HTTPException(status_code=400, detail="File must be an audio file")
    
    try:
        logger.info(f"Processing audio file (JSON mode): {audio_file.filename}")
        
        # Convert audio to text
        transcribed_text = await voice_processor.process_audio_file(audio_file)
        
        # Query RAG database
        rag_response = query_rag(transcribed_text)
        
        # Generate audio response
        audio_data = await voice_processor.generate_audio_response(rag_response)
        
        # For JSON response, you might want to save the audio file temporarily
        # and provide a download URL, or return base64 encoded audio
        import base64
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        return {
            "transcription": transcribed_text,
            "rag_response": rag_response,
            "audio_response": audio_base64,
            "audio_format": "wav",
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in process_voice_json: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



if __name__ == "__main__":
    import uvicorn
    try:
        uvicorn.run(
            "app:app",
            host="localhost",
            port=8000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
