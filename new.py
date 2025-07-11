import edge_tts
import os
import re

def process_uploaded_file(file):
    """Process uploaded file and extract text content"""
    if file is None:
        return None, None
    
    try:
        file_path = file.name if hasattr(file, 'name') else file
        file_extension = os.path.splitext(file_path)[1].lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's an SRT file and extract text only
        if file_extension == '.srt' or re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', content, re.MULTILINE):
            # Parse SRT and extract only text
            lines = content.split('\n')
            text_only = []
            
            i = 0
            while i < len(lines):
                if not lines[i].strip():
                    i += 1
                    continue
                    
                # Check if this is a subtitle number line
                if lines[i].strip().isdigit():
                    i += 1
                    if i >= len(lines):
                        break
                        
                    # Skip timestamp line
                    if re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[i]):
                        i += 1
                        subtitle_text = ""
                        
                        # Collect all text lines until empty line or end of file
                        while i < len(lines) and lines[i].strip():
                            subtitle_text += lines[i] + " "
                            i += 1
                        
                        subtitle_text = subtitle_text.strip()
                        text_only.append(subtitle_text)
                else:
                    i += 1
            
            return " ".join(text_only), content
        else:
            # Treat as plain text
            return content, content
        
    except Exception as e:
        return f"Error processing file: {str(e)}", None

async def text_to_speech(text, voice, rate, pitch, uploaded_file=None):
    """Convert text to speech"""
    if not text.strip() and uploaded_file is None:
        return None, "Please enter text or upload a file to convert."
    if not voice:
        return None, "Please select a voice."
    
    # Process uploaded file if provided
    if uploaded_file is not None:
        file_text, _ = process_uploaded_file(uploaded_file)
        if isinstance(file_text, str) and file_text.strip():
            text = file_text
        
    voice_short_name = voice.split(" - ")[0]
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"
    
    # Set audio output path as MP3
    audio_path = "voice_recording.mp3"
    
    # Generate speech and save directly as MP3
    communicate = edge_tts.Communicate(text, voice_short_name, rate=rate_str, pitch=pitch_str)
    await communicate.save(audio_path)
    
    return audio_path, None