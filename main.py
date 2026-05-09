# main.py
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import yt_dlp
import os
from datetime import timedelta
import subprocess
import uuid

app = FastAPI(title="YouTube Audio Cleaner")

class VideoRequest(BaseModel):
    youtube_url: str
    start_time: str   # e.g. "1:45" or "105"
    end_time: str     # e.g. "4:20" or "260"

def time_to_seconds(time_str: str) -> int:
    if ':' in time_str:
        parts = time_str.split(':')
        if len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    return int(time_str)

@app.post("/process")
async def process_video(request: VideoRequest):
    job_id = str(uuid.uuid4())[:8]
    output_dir = f"temp/{job_id}"
    os.makedirs(output_dir, exist_ok=True)

    try:
        # 1. Download audio as WAV
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_dir}/original.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(request.youtube_url, download=True)
            wav_path = f"{output_dir}/original.wav"

        # 2. Trim audio
        start_sec = time_to_seconds(request.start_time)
        end_sec = time_to_seconds(request.end_time)
        duration = end_sec - start_sec

        trimmed_path = f"{output_dir}/trimmed.wav"
        subprocess.run([
            'ffmpeg', '-y', '-i', wav_path,
            '-ss', str(start_sec), '-t', str(duration),
            '-acodec', 'pcm_s16le', '-ar', '44100',
            trimmed_path
        ], check=True)

        # 3. Noise Reduction (using RNNoise via ffmpeg filter - good quality)
        final_path = f"{output_dir}/final_clean.wav"
        subprocess.run([
            'ffmpeg', '-y', '-i', trimmed_path,
            '-af', 'arnndn=m=~/.rnnoise-models/speech.rnnn',  # You can improve this
            '-acodec', 'pcm_s16le', '-ar', '44100',
            final_path
        ], check=True)

        return FileResponse(
            final_path,
            media_type='audio/wav',
            filename=f"clean_audio_{job_id}.wav"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
