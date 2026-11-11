"""FastAPI application for MP3 to MIDI conversion and file system management."""

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.converter import convert_audio_to_midi, generate_demo_audio

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
MIDIS_DIR = DATA_DIR / "midis"
METADATA_FILE = DATA_DIR / "metadata.json"
FRONTEND_DIR = BASE_DIR / "frontend"

for d in [DATA_DIR, UPLOADS_DIR, MIDIS_DIR, FRONTEND_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Audio to MIDI Converter & File System",
    description="Full-stack MP3 to MIDI converter with instant mobile and PC downloads and full file management",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "Content-Length", "Content-Type"],
)

def load_metadata() -> Dict[str, Any]:
    if not METADATA_FILE.exists():
        return {}
    try:
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_metadata(meta: Dict[str, Any]) -> None:
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

def format_file_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if unit != 'B' else f"{bytes_size} B"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": time.time()}

@app.get("/api/stats")
async def get_system_stats():
    meta = load_metadata()
    total_files = len(meta)
    total_audio_bytes = sum(item.get("audio_size", 0) for item in meta.values())
    total_midi_bytes = sum(item.get("midi_size", 0) for item in meta.values())
    total_notes = sum(item.get("notes_count", 0) for item in meta.values())

    return {
        "total_files": total_files,
        "total_audio_size": format_file_size(total_audio_bytes),
        "total_midi_size": format_file_size(total_midi_bytes),
        "total_notes_converted": total_notes,
        "storage_dir": str(DATA_DIR)
    }

@app.get("/api/files")
async def list_files():
    meta = load_metadata()
    # Sort files by created_at descending
    files_list = sorted(
        meta.values(),
        key=lambda x: x.get("created_at", 0),
        reverse=True
    )
    return {"files": files_list, "count": len(files_list)}

@app.post("/api/convert")
async def upload_and_convert(
    file: UploadFile = File(...),
    bpm: int = Form(120),
    sensitivity: float = Form(0.5),
    mode: str = Form("polyphonic"),
    instrument: int = Form(0)
):
    original_filename = file.filename or "audio.mp3"
    stem = Path(original_filename).stem
    ext = Path(original_filename).suffix.lower()
    if not ext:
        ext = ".mp3"

    allowed_exts = {".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".aiff"}
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{ext}'. Supported: {', '.join(allowed_exts)}"
        )

    file_id = str(uuid.uuid4())
    audio_filename = f"{file_id}{ext}"
    midi_filename = f"{file_id}.mid"

    audio_path = UPLOADS_DIR / audio_filename
    midi_path = MIDIS_DIR / midi_filename

    # Save uploaded audio file
    try:
        with open(audio_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {str(e)}")

    audio_size = audio_path.stat().st_size

    # Convert audio to MIDI
    try:
        result = convert_audio_to_midi(
            input_audio_path=audio_path,
            output_midi_path=midi_path,
            bpm=bpm,
            sensitivity=sensitivity,
            mode=mode,
            instrument=instrument
        )
    except Exception as e:
        # Cleanup audio on failure
        if audio_path.exists():
            audio_path.unlink()
        raise HTTPException(status_code=500, detail=f"Audio conversion failed: {str(e)}")

    midi_size = midi_path.stat().st_size if midi_path.exists() else 0

    record = {
        "id": file_id,
        "original_name": original_filename,
        "stem_name": stem,
        "audio_file": audio_filename,
        "midi_file": midi_filename,
        "audio_size": audio_size,
        "audio_size_formatted": format_file_size(audio_size),
        "midi_size": midi_size,
        "midi_size_formatted": format_file_size(midi_size),
        "created_at": time.time(),
        "created_at_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "bpm": bpm,
        "sensitivity": sensitivity,
        "mode": mode,
        "notes_count": result.get("notes_count", 0),
        "duration_sec": result.get("duration_sec", 0),
        "notes_sample": result.get("notes_sample", [])
    }

    meta = load_metadata()
    meta[file_id] = record
    save_metadata(meta)

    return {
        "success": True,
        "message": "Conversion successful",
        "file": record,
        "download_url": f"/api/files/{file_id}/download/midi",
        "audio_url": f"/api/files/{file_id}/download/audio"
    }

@app.post("/api/generate-demo")
async def create_demo_melody(mode: str = Form("polyphonic"), bpm: int = Form(120)):
    file_id = f"demo-{uuid.uuid4().hex[:8]}"
    original_filename = "demo_melody_c_major.mp3"
    stem = "demo_melody_c_major"

    audio_filename = f"{file_id}.mp3"
    midi_filename = f"{file_id}.mid"

    audio_path = UPLOADS_DIR / audio_filename
    midi_path = MIDIS_DIR / midi_filename

    # Generate demo audio
    generate_demo_audio(audio_path)
    audio_size = audio_path.stat().st_size

    result = convert_audio_to_midi(
        input_audio_path=audio_path,
        output_midi_path=midi_path,
        bpm=bpm,
        sensitivity=0.5,
        mode=mode,
        instrument=0
    )

    midi_size = midi_path.stat().st_size

    record = {
        "id": file_id,
        "original_name": original_filename,
        "stem_name": stem,
        "audio_file": audio_filename,
        "midi_file": midi_filename,
        "audio_size": audio_size,
        "audio_size_formatted": format_file_size(audio_size),
        "midi_size": midi_size,
        "midi_size_formatted": format_file_size(midi_size),
        "created_at": time.time(),
        "created_at_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
        "bpm": bpm,
        "sensitivity": 0.5,
        "mode": mode,
        "notes_count": result.get("notes_count", 0),
        "duration_sec": result.get("duration_sec", 0),
        "notes_sample": result.get("notes_sample", [])
    }

    meta = load_metadata()
    meta[file_id] = record
    save_metadata(meta)

    return {
        "success": True,
        "message": "Sample demo melody generated and converted",
        "file": record,
        "download_url": f"/api/files/{file_id}/download/midi",
        "audio_url": f"/api/files/{file_id}/download/audio"
    }

@app.get("/api/files/{file_id}/download/{file_format}")
async def download_file(file_id: str, file_format: str):
    """Serve file for immediate download to Phone or PC with direct attachment headers."""
    meta = load_metadata()
    if file_id not in meta:
        raise HTTPException(status_code=404, detail="File record not found in system")

    record = meta[file_id]
    base_name = record.get("stem_name", "converted_music")

    if file_format == "midi":
        file_path = MIDIS_DIR / record["midi_file"]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="MIDI file not found on disk")
        download_name = f"{base_name}.mid"
        media_type = "audio/midi"
    elif file_format == "audio":
        file_path = UPLOADS_DIR / record["audio_file"]
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found on disk")
        download_name = record.get("original_name", "audio.mp3")
        media_type = "audio/mpeg" if file_path.suffix == ".mp3" else "application/octet-stream"
    else:
        raise HTTPException(status_code=400, detail="Invalid format requested. Use 'midi' or 'audio'.")

    # Mobile & PC immediate download headers
    headers = {
        "Content-Disposition": f'attachment; filename="{download_name}"',
        "Content-Type": media_type,
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0"
    }

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type=media_type,
        headers=headers
    )

@app.get("/api/files/{file_id}/stream-audio")
async def stream_audio(file_id: str):
    """Stream audio for inline web player preview without forcing attachment download."""
    meta = load_metadata()
    if file_id not in meta:
        raise HTTPException(status_code=404, detail="File record not found")
    record = meta[file_id]
    file_path = UPLOADS_DIR / record["audio_file"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")
    media_type = "audio/mpeg" if file_path.suffix == ".mp3" else "audio/wav"
    return FileResponse(path=str(file_path), media_type=media_type)

@app.delete("/api/files/{file_id}")
async def delete_file_record(file_id: str):
    """Delete a converted item from file system and metadata."""
    meta = load_metadata()
    if file_id not in meta:
        raise HTTPException(status_code=404, detail="File record not found")

    record = meta.pop(file_id)
    save_metadata(meta)

    # Delete audio file
    audio_path = UPLOADS_DIR / record.get("audio_file", "")
    if audio_path.exists():
        try:
            audio_path.unlink()
        except Exception:
            pass

    # Delete MIDI file
    midi_path = MIDIS_DIR / record.get("midi_file", "")
    if midi_path.exists():
        try:
            midi_path.unlink()
        except Exception:
            pass

    return {"success": True, "message": f"Deleted {record.get('original_name')}"}

# Mount static frontend directory
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
