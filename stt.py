from vosk import Model, KaldiRecognizer
import wave
import json
from pydub import AudioSegment

audio = AudioSegment.from_wav("voice_recording.wav")
audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
audio.export("voice_recording.wav", format="wav")

wf = wave.open("voice_recording.wav", "rb")
model = Model("vosk-model-small-en-us-0.15")  # Download from https://alphacephei.com/vosk/models
rec = KaldiRecognizer(model, wf.getframerate())

while True:
    data = wf.readframes(4000)
    if len(data) == 0:
        break
    if rec.AcceptWaveform(data):
        print(json.loads(rec.Result())["text"])
