import os
import io
from dotenv import load_dotenv
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
from google import genai
from model import query_rag
from google.genai import types
import soundfile as sf

threshold = 0.50  # Adjust for your mic sensitivity
samplerate = 44100
chunk_duration =2   # seconds
silence_limit = 2.0  # seconds before stopping

recording = []
silent_chunks = 0
max_silent_chunks = int(silence_limit / chunk_duration)

print("🎤 Listening... Speak now!")

while True:
    audio_chunk = sd.rec(int(chunk_duration * samplerate), samplerate=samplerate, channels=1)
    sd.wait()
    volume = np.linalg.norm(audio_chunk)

    if volume > threshold:
        print("Recording...")
        recording.append(audio_chunk)
        silent_chunks = 0
    elif recording:
        silent_chunks += 1
        recording.append(audio_chunk)
        if silent_chunks > max_silent_chunks:
            print("🛑 Silence detected. Stopping...")
            break

if recording:
    audio_np = np.concatenate(recording, axis=0)
    wav.write("voice_recording.wav", samplerate, audio_np)
    print("Saved as voice_recording.wav")
else:
    print("No audio detected.")


load_dotenv()
client = genai.Client(api_key=os.getenv('google_api'))

myfile = client.files.upload(file="voice_recording.wav")

response = client.models.generate_content(
    model="gemini-2.0-flash", contents=["change this audio to text", myfile]
)

res = query_rag(response.text)




# Set up the wave file to save the output:
# def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
#    with wave.open(filename, "wb") as wf:
#       wf.setnchannels(channels)
#       wf.setsampwidth(sample_width)
#       wf.setframerate(rate)
#       wf.writeframes(pcm)

client = genai.Client(api_key=os.getenv('google_api'))

response = client.models.generate_content(
   model="gemini-2.5-flash-preview-tts",
   contents="Say cheerfully: "+ res ,
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

data = response.candidates[0].content.parts[0].inline_data.data
print("Audio generation complete")
# file_name='output.wav'
# wave_file(file_name, data)

audio_stream = io.BytesIO(data)

# Decode from binary stream - specify format for BytesIO
audio_data, sample_rate = sf.read(audio_stream, dtype='float32', format='RAW', subtype='PCM_16', samplerate=24000, channels=1)

# Play it directly
sd.play(audio_data, sample_rate)
sd.wait()