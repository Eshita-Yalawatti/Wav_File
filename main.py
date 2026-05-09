from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import yt_dlp
import os
import subprocess
import uuid
from pathlib import Path

app = FastAPI(title="YouTube Audio Cleaner")

# === ADD THIS CORS CONFIGURATION ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # Allow all (for GitHub Pages)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class VideoRequest(BaseModel):
    youtube_url: str
    start_time: str
    end_time: str

def time_to_seconds(time_str: str) -> int:
    if ':' in time_str:
        parts = list(map(int, time_str.replace(":", ":").split(':')))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        elif len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
    return int(time_str)

@app.post("/process")
async def process_video(request: VideoRequest):
    job_id = str(uuid.uuid4())[:8]
    output_dir = Path(f"temp/{job_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Download audio
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{output_dir}/original.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'wav'}],
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(request.youtube_url, download=True)

        original_wav = next(output_dir.glob("original*.wav"))

        # Trim
        start_sec = time_to_seconds(request.start_time)
        end_sec = time_to_seconds(request.end_time)
        duration = end_sec - start_sec

        trimmed_path = output_dir / "trimmed.wav"
        subprocess.run([
            'ffmpeg', '-y', '-i', str(original_wav),
            '-ss', str(start_sec), '-t', str(duration),
            '-acodec', 'pcm_s16le', '-ar', '44100',
            str(trimmed_path)
        ], check=True, capture_output=True)

        # Noise Reduction
        final_path = output_dir / "final_clean.wav"
        subprocess.run([
            'ffmpeg', '-y', '-i', str(trimmed_path),
            '-af', 'afftdn=nr=20:nf=-40',
            '-acodec', 'pcm_s16le', '-ar', '44100',
            str(final_path)
        ], check=True, capture_output=True)

        return FileResponse(
            final_path,
            media_type="audio/wav",
            filename="clean_audio.wav"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
    finally:
        # Cleanup temp files (optional)
        pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
