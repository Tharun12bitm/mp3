"""Integration and unit tests for FastAPI backend and conversion endpoints."""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app import app, load_metadata, save_metadata, DATA_DIR, UPLOADS_DIR, MIDIS_DIR

client = TestClient(app)

def test_health():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_stats_empty():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_files" in data
    assert "storage_dir" in data

def test_generate_demo_endpoint():
    response = client.post("/api/generate-demo", data={"mode": "melody", "bpm": 120})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    file_id = data["file"]["id"]
    assert file_id.startswith("demo-")
    assert data["file"]["notes_count"] > 0
    assert "download_url" in data

    # Verify download midi
    midi_resp = client.get(f"/api/files/{file_id}/download/midi")
    assert midi_resp.status_code == 200
    assert "attachment" in midi_resp.headers.get("content-disposition", "")
    assert len(midi_resp.content) > 0

    # Verify download audio
    audio_resp = client.get(f"/api/files/{file_id}/download/audio")
    assert audio_resp.status_code == 200
    assert "attachment" in audio_resp.headers.get("content-disposition", "")
    assert len(audio_resp.content) > 0

    # Verify stream audio
    stream_resp = client.get(f"/api/files/{file_id}/stream-audio")
    assert stream_resp.status_code == 200

    # Verify listing
    list_resp = client.get("/api/files")
    assert list_resp.status_code == 200
    files = list_resp.json()["files"]
    assert any(f["id"] == file_id for f in files)

    # Verify delete
    del_resp = client.delete(f"/api/files/{file_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # Check 404 after deletion
    after_resp = client.get(f"/api/files/{file_id}/download/midi")
    assert after_resp.status_code == 404

def test_upload_and_convert_custom_audio(tmp_path):
    # Create small test wav
    import numpy as np
    import scipy.io.wavfile as wavfile
    sample_rate = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    # 440 Hz (A4)
    sig = 0.5 * np.sin(2 * np.pi * 440.0 * t)
    wav_path = tmp_path / "test_a4.wav"
    wavfile.write(str(wav_path), sample_rate, (sig * 32767).astype(np.int16))

    with open(wav_path, "rb") as f:
        response = client.post(
            "/api/convert",
            files={"file": ("test_a4.wav", f, "audio/wav")},
            data={"bpm": 100, "sensitivity": 0.6, "mode": "melody"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    file_id = data["file"]["id"]
    assert data["file"]["original_name"] == "test_a4.wav"
    assert data["file"]["notes_count"] >= 1
    # Check that note detected has pitch ~69 (A4)
    pitches = [n["pitch"] for n in data["file"]["notes_sample"]]
    assert 69 in pitches

    # Cleanup
    client.delete(f"/api/files/{file_id}")
