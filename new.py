import edge_tts
import tempfile
import os
import re

def format_time(milliseconds):
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
    # Ensure milliseconds is an integer
    milliseconds = int(milliseconds)
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

def time_to_ms(time_str):
    """Convert SRT time format (HH:MM:SS,mmm) to milliseconds"""
    hours, minutes, rest = time_str.split(':')
    seconds, milliseconds = rest.split(',')
    return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)

def parse_srt_content(content):
    """Parse SRT file content and extract text and timing data"""
    lines = content.split('\n')
    timing_data = []
    text_only = []
    
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
            
        # Check if this is a subtitle number line
        if lines[i].strip().isdigit():
            subtitle_num = int(lines[i].strip())
            i += 1
            if i >= len(lines):
                break
                
            # Parse timestamp line
            timestamp_match = re.search(r'(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})', lines[i])
            if timestamp_match:
                start_time = timestamp_match.group(1)
                end_time = timestamp_match.group(2)
                
                # Convert to milliseconds
                start_ms = time_to_ms(start_time)
                end_ms = time_to_ms(end_time)
                
                i += 1
                subtitle_text = ""
                
                # Collect all text lines until empty line or end of file
                while i < len(lines) and lines[i].strip():
                    subtitle_text += lines[i] + " "
                    i += 1
                
                subtitle_text = subtitle_text.strip()
                text_only.append(subtitle_text)
                timing_data.append({
                    'text': subtitle_text,
                    'start': start_ms,
                    'end': end_ms
                })
        else:
            i += 1
    
    return " ".join(text_only), timing_data

def process_uploaded_file(file):
    """Process uploaded file and detect if it's SRT or plain text"""
    if file is None:
        return None, None, False, None
    
    try:
        file_path = file.name if hasattr(file, 'name') else file
        file_extension = os.path.splitext(file_path)[1].lower()
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check if it's an SRT file
        is_subtitle = False
        timing_data = None
        
        if file_extension == '.srt' or re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', content, re.MULTILINE):
            is_subtitle = True
            text_content, timing_data = parse_srt_content(content)
            # Return original content for display
            return text_content, timing_data, is_subtitle, content
        else:
            # Treat as plain text
            text_content = content
        
        return text_content, timing_data, is_subtitle, content
    except Exception as e:
        return f"Error processing file: {str(e)}", None, False, None

async def text_to_speech(text, voice, rate, pitch, generate_subtitles=False, uploaded_file=None):
    """Convert text to speech, handling both direct text input and uploaded files"""
    if not text.strip() and uploaded_file is None:
        return None, None, "Please enter text or upload a file to convert."
    if not voice:
        return None, None, "Please select a voice."

    # First, determine if the text is SRT format
    is_srt_format = bool(re.search(r'^\d+\s*\n\d{2}:\d{2}:\d{2},\d{3}\s*-->\s*\d{2}:\d{2}:\d{2},\d{3}', text, re.MULTILINE))
    
    # If the text is in SRT format, parse it directly
    if is_srt_format:
        text_content, timing_data = parse_srt_content(text)
        is_subtitle = True
    else:
        # Process uploaded file if provided
        timing_data = None
        is_subtitle = False
        
        if uploaded_file is not None:
            file_text, file_timing_data, file_is_subtitle, _ = process_uploaded_file(uploaded_file)
            if isinstance(file_text, str) and file_text.strip():
                if file_is_subtitle:
                    text = file_text
                    timing_data = file_timing_data
                    is_subtitle = file_is_subtitle

    voice_short_name = voice.split(" - ")[0]
    rate_str = f"{rate:+d}%"
    pitch_str = f"{pitch:+d}Hz"
    
    # Create temporary file for audio
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
        audio_path = tmp_file.name
    
    subtitle_path = None
    
    # Handle SRT-formatted text or subtitle files differently for audio generation
    if is_srt_format or (is_subtitle and timing_data):
        # Create separate audio files for each subtitle entry and then combine them
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_segments = []
            max_end_time = 0
            
            # If we don't have timing data but have SRT format text, parse it
            if not timing_data and is_srt_format:
                _, timing_data = parse_srt_content(text)
            
            # Process each subtitle entry separately
            for i, entry in enumerate(timing_data):
                segment_text = entry['text']
                start_time = entry['start']
                end_time = entry['end']
                max_end_time = max(max_end_time, end_time)
                
                # Create temporary file for this segment
                segment_file = os.path.join(temp_dir, f"segment_{i}.mp3")
                
                # Generate audio for this segment
                communicate = edge_tts.Communicate(segment_text, voice_short_name, rate=rate_str, pitch=pitch_str)
                communicate.save(segment_file)
                
                audio_segments.append({
                    'file': segment_file,
                    'start': start_time,
                    'end': end_time,
                    'text': segment_text
                })
            
            # Combine audio segments with proper timing
            import wave
            import audioop
            from pydub import AudioSegment
            
            # Initialize final audio
            final_audio = AudioSegment.silent(duration=max_end_time + 1000)  # Add 1 second buffer
            
            # Add each segment at its proper time
            for segment in audio_segments:
                segment_audio = AudioSegment.from_file(segment['file'])
                final_audio = final_audio.overlay(segment_audio, position=segment['start'])
            
            # Export the combined audio
            final_audio.export(audio_path, format="mp3")
            
            # Generate subtitles if requested
            if generate_subtitles:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as srt_file:
                    subtitle_path = srt_file.name
                    with open(subtitle_path, "w", encoding="utf-8") as f:
                        for i, entry in enumerate(timing_data):
                            f.write(f"{i+1}\n")
                            f.write(f"{format_time(entry['start'])} --> {format_time(entry['end'])}\n")
                            f.write(f"{entry['text']}\n\n")
    else:
        # Use the existing approach for regular text
        communicate = edge_tts.Communicate(text, voice_short_name, rate=rate_str, pitch=pitch_str)
        if not generate_subtitles:
            await communicate.save(audio_path)
        if generate_subtitles:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".srt") as srt_file:
                subtitle_path = srt_file.name
                
            # Generate audio and collect word boundary data
            async def process_audio():
                word_boundaries = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        with open(audio_path, "ab") as audio_file:
                            audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        word_boundaries.append(chunk)
                return word_boundaries
            
            word_boundaries = process_audio()
            
            # Group words into sensible phrases/sentences for subtitles
            phrases = []
            current_phrase = []
            current_text = ""
            phrase_start = 0
            
            for i, boundary in enumerate(word_boundaries):
                word = boundary["text"]
                start_time = boundary["offset"] / 10000
                duration = boundary["duration"] / 10000
                end_time = start_time + duration
                
                if not current_phrase:
                    phrase_start = start_time
                    
                current_phrase.append(boundary)
                
                if word in ['.', ',', '!', '?', ':', ';'] or word.startswith(('.', ',', '!', '?', ':', ';')):
                    current_text = current_text.rstrip() + word + " "
                else:
                    current_text += word + " "
                
                # Determine if we should end this phrase and start a new one
                should_break = False
                
                # Break on punctuation
                if word.endswith(('.', '!', '?', ':', ';', ',')) or i == len(word_boundaries) - 1:
                    should_break = True
                    
                # Break after a certain number of words (4-5 is typical for subtitles)
                elif len(current_phrase) >= 5:
                    should_break = True
                    
                # Break on long pause (more than 300ms between words)
                elif i < len(word_boundaries) - 1:
                    next_start = word_boundaries[i + 1]["offset"] / 10000
                    if next_start - end_time > 300:
                        should_break = True
            
                if should_break or i == len(word_boundaries) - 1:
                    if current_phrase:
                        last_boundary = current_phrase[-1]
                        phrase_end = (last_boundary["offset"] + last_boundary["duration"]) / 10000
                        phrases.append({
                            "text": current_text.strip(),
                            "start": phrase_start,
                            "end": phrase_end
                        })
                        current_phrase = []
                        current_text = ""
            
            # Write phrases to SRT file
            with open(subtitle_path, "w", encoding="utf-8") as srt_file:
                for i, phrase in enumerate(phrases):
                    # Write SRT entry
                    srt_file.write(f"{i+1}\n")
                    srt_file.write(f"{format_time(phrase['start'])} --> {format_time(phrase['end'])}\n")
                    srt_file.write(f"{phrase['text']}\n\n")
    
    return audio_path, subtitle_path, None