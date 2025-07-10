import requests
import json
from playsound import playsound
import os
from pathlib import Path
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import asyncio
from tts import text_to_speech
import time
from vosk import Model, KaldiRecognizer
import wave
from pydub import AudioSegment
import sys
sys.stdout.reconfigure(encoding='utf-8')


async def run_tts(context):
    audio_path, subtitle_path, warning =await text_to_speech(
        text=context,
        voice="en-IN-NeerjaNeural - en-IN (Female)",  # Use a valid voice key from your app
        rate=0,
        pitch=0,
        generate_subtitles=False,
        uploaded_file=None
    )
    return audio_path

def calculate_volume(chunk):
    return np.sqrt(np.mean(chunk**2))

def record():

    print("\n🎧 Processing audio file...")

    # Separate thresholds
    start_threshold = 0.05       # Start recording above this
    silence_threshold = 0.03     # Stop recording if below this for long enough

    samplerate = 44100
    chunk_duration = 2  # seconds
    silence_limit = 2.0  # seconds of silence to stop

    recording = []
    silent_chunks = 0
    max_silent_chunks = int(silence_limit / chunk_duration)

    print("🎤 Listening... Speak now!")

    recording_started = False

    while True:
        audio_chunk = sd.rec(int(chunk_duration * samplerate), samplerate=samplerate, channels=1, dtype='float32')
        sd.wait()
        volume = calculate_volume(audio_chunk)
        print(f"🔊 Volume: {volume:.5f}")

        if not recording_started:
            if volume > start_threshold:
                print("🎙️ Recording started...")
                recording_started = True
                recording.append(audio_chunk)
        else:
            recording.append(audio_chunk)
            if volume < silence_threshold:
                silent_chunks += 1
                print(f"🕑 Silence chunk {silent_chunks}/{max_silent_chunks}")
            else:
                silent_chunks = 0

            if silent_chunks >= max_silent_chunks:
                print("🛑 Silence detected. Stopping...")
                break

    if recording:
        audio_np = np.concatenate(recording, axis=0)
        wav.write("voice_recording.wav", samplerate, audio_np)
        print("Saved as voice_recording.wav")
    else:
        print("No audio detected.")
    
    


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
    
    def process_audio_file(self, audio_file_path):
        """
        Send audio file to API and get processed response.
        
        Args:
            audio_file_path: Path to audio file
            return_audio_file: If True, returns audio file, else returns JSON
        """
        try:
            with open(audio_file_path, 'rb') as f:
                files = {'audio_file': (Path(audio_file_path).name, f, 'audio/wav')}
                response = requests.post(f"{self.base_url}/process-voice", files=files)
            
            if response.status_code == 200:
                response = response.json() 
                return response
            else:
                return {"error": f"API Error: {response.status_code} - {response.text}"}
                
                    
        except Exception as e:
            return {"error": str(e)}
    
    def process_text_file(self, audio_file_path):
        audio = AudioSegment.from_wav(audio_file_path)
        audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
        audio.export("voice_recording.wav", format="wav")

        wf = wave.open("voice_recording.wav", "rb")
        model = Model("vosk-model-small-en-us-0.15")  # Download from https://alphacephei.com/vosk/models
        rec = KaldiRecognizer(model, wf.getframerate())
        text =""
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                text= text+(json.loads(rec.Result())["text"])
        print("Question: ",text)
        try:
            response = requests.post(
                f"{self.base_url}/process-text",
                json={"question": text}
            )

            print(response.json())
            
            if response.status_code == 200:
                response = response.json() 
                return response
            else:
                return {"error": f"API Error: {response.status_code} - {response.text}"}
                
                    
        except Exception as e:
            return {"error": str(e)}


    # Initialize client 157.245.102.4
client = VoiceRAGClient("http://localhost:8000")  # Change to your server URL

print(" Checking API health...")
health = client.health_check()
print(f"Health status: {json.dumps(health, indent=2)}")

if "error" in health:
    print(" API is not accessible!")
    
else:
    if False:
        record()
    audio_file = 'voice_recording.wav'
    if Path(audio_file).exists():
        s = time.perf_counter()
        result = client.process_text_file(audio_file)
        e = time.perf_counter()
        print(e-s)
        s = time.perf_counter()
        audio = asyncio.run(run_tts(result["response"]))
        e = time.perf_counter()
        print(e-s)
        print(result["response"])         
        playsound(audio)
    
    else:
        print(f" Audio file {audio_file} not found!")
    
    os.remove(audio)
    