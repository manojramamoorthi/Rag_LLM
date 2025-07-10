import subprocess
import os

def record_voice(output_path="voice_recording.wav"):
    command = [
        "sox",
        "-t", "waveaudio", "default",
        output_path,
        "silence", "1", "0.1", "5%", "1", "2.0", "5%"
    ]

    try:
        subprocess.run(command, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Recording failed: {e}")
        return None

# Example usage
audio_file = record_voice()
print(f"Saved to: {audio_file}")
