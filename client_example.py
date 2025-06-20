import requests
import json
import base64
import soundfile as sf
import sounddevice as sd
import io
from pathlib import Path

class VoiceRAGClient:
    def __init__(self, base_url="http://0.0.0.0:8000"):
        self.base_url = base_url
        
    def health_check(self):
        """Check if the API is healthy and ready."""
        try:
            response = requests.get(f"{self.base_url}/health")
            return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    def process_audio_file(self, audio_file_path, return_audio_file=True):
        """
        Send audio file to API and get processed response.
        
        Args:
            audio_file_path: Path to audio file
            return_audio_file: If True, returns audio file, else returns JSON
        """
        try:
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (Path(audio_file_path).name, f, 'audio/wav')}
                
                if return_audio_file:
                    # Get audio response
                    response = requests.post(f"{self.base_url}/process-voice", files=files)
                    
                    if response.status_code == 200:
                        # Save and play the response audio
                        with open("response_audio.wav", "wb") as audio_file:
                            audio_file.write(response.content)
                        
                        # Play the audio
                        self.play_audio("response_audio.wav")
                        
                        return {"status": "success", "audio_saved": "response_audio.wav"}
                    else:
                        return {"error": f"API Error: {response.status_code} - {response.text}"}
                else:
                    # Get JSON response
                    response = requests.post(f"{self.base_url}/process-voice-json", files=files)
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        # Decode and save audio from base64
                        if 'audio_response' in data:
                            audio_data = base64.b64decode(data['audio_response'])
                            with open("response_audio.wav", "wb") as audio_file:
                                audio_file.write(audio_data)
                            
                            # Play the audio
                            self.play_audio("response_audio.wav")
                        
                        return data
                    else:
                        return {"error": f"API Error: {response.status_code} - {response.text}"}
                        
        except Exception as e:
            return {"error": str(e)}
    
    def speech_to_text(self, audio_file_path):
        """Convert audio file to text only."""
        try:
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (Path(audio_file_path).name, f, 'audio/wav')}
                response = requests.post(f"{self.base_url}/speech-to-text", files=files)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"API Error: {response.status_code} - {response.text}"}
                    
        except Exception as e:
            return {"error": str(e)}
    
    def text_to_speech(self, text, save_path="tts_output.wav"):
        """Convert text to speech and save/play it."""
        try:
            data = {"text": text}
            response = requests.post(f"{self.base_url}/text-to-speech", params=data)
            
            if response.status_code == 200:
                with open(save_path, "wb") as audio_file:
                    audio_file.write(response.content)
                
                # Play the audio
                self.play_audio(save_path)
                
                return {"status": "success", "audio_saved": save_path}
            else:
                return {"error": f"API Error: {response.status_code} - {response.text}"}
                
        except Exception as e:
            return {"error": str(e)}
    
    def play_audio(self, audio_file_path):
        """Play audio file using sounddevice."""
        try:
            data, samplerate = sf.read(audio_file_path)
            sd.play(data, samplerate)
            sd.wait()  # Wait until the audio finishes playing
            print(f"✅ Played audio: {audio_file_path}")
        except Exception as e:
            print(f"❌ Error playing audio: {e}")

# Example usage
def main():
    # Initialize client
    client = VoiceRAGClient("http://localhost:8000")  # Change to your server URL
    
    print("🔍 Checking API health...")
    health = client.health_check()
    print(f"Health status: {json.dumps(health, indent=2)}")
    
    if "error" in health:
        print("❌ API is not accessible!")
        return
    
    # Example 1: Process audio file and get audio response
    print("\n🎤 Processing audio file...")
    audio_file = "test_audio.wav"  # Replace with your audio file path
    
    if Path(audio_file).exists():
        result = client.process_audio_file(audio_file, return_audio_file=True)
        print(f"Result: {json.dumps(result, indent=2)}")
    else:
        print(f"❌ Audio file {audio_file} not found!")
    
    # Example 2: Get JSON response with transcription and RAG response
    if Path(audio_file).exists():
        print("\n📋 Getting JSON response...")
        result = client.process_audio_file(audio_file, return_audio_file=False)
        print(f"Transcription: {result.get('transcription', 'N/A')}")
        print(f"RAG Response: {result.get('rag_response', 'N/A')}")
    
    # Example 3: Text to speech
    print("\n🗣️ Converting text to speech...")
    tts_result = client.text_to_speech("Hello! This is a test of the text to speech functionality.")
    print(f"TTS Result: {json.dumps(tts_result, indent=2)}")
    
    # Example 4: Speech to text only
    if Path(audio_file).exists():
        print("\n📝 Converting speech to text...")
        stt_result = client.speech_to_text(audio_file)
        print(f"STT Result: {json.dumps(stt_result, indent=2)}")

if __name__ == "__main__":
    main()