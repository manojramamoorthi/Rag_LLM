import requests
import json
import base64
import soundfile as sf
import sounddevice as sd
import io
from pathlib import Path

class VoiceRAGClient:
    def __init__(self, base_url="http://localhost:8000"):
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
                    response = requests.post(f"{self.base_url}/process-voice", files=files)
                    if response.status_code == 200:
                        response = response.json()
                        audio_data = base64.b64decode(response['audio_base64'])
                        audio_stream = io.BytesIO(audio_data)

                        # Decode from binary stream - specify format for BytesIO
                        audio_data, sample_rate = sf.read(audio_stream, dtype='float32', format='RAW', subtype='PCM_16', samplerate=24000, channels=1)
                        
                        # Play the audio
                        sd.play(audio_data,sample_rate)
                        sd.wait()

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

# Example usage
def main():
    # Initialize client 143.244.130.47
    client = VoiceRAGClient("http://localhost:8000")  # Change to your server URL
    
    print(" Checking API health...")
    health = client.health_check()
    print(f"Health status: {json.dumps(health, indent=2)}")
    
    if "error" in health:
        print(" API is not accessible!")
        return
    
    # Example 1: Process audio file and get audio response
    print("\n Processing audio file...")
    audio_file = "voice_recording.wav"  # Replace with your audio file path
    
    if Path(audio_file).exists():
        result = client.process_audio_file(audio_file, return_audio_file=True)
    else:
        print(f" Audio file {audio_file} not found!")
    print(result)
    

if __name__ == "__main__":
    main()