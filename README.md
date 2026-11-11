# MidiPulse: Full-Stack MP3 to MIDI Converter & File System

A modern full-stack web application for transcribing MP3, WAV, OGG, FLAC, and other audio formats into standard MIDI (.mid) files with an integrated file system and immediate download on mobile phones (iOS / Android) and PC.

## Features
- **Audio to MIDI Transcription Engine**: Uses `ffmpeg` for multi-format audio decoding and signal processing (STFT spectral peak tracking, onset detection, and harmonic filtering) to extract polyphonic notes, melody solos, or basslines.
- **Immediate Phone & PC Downloads**: One-click instant direct attachment downloads with standard MIME types and direct download triggers.
- **Full File System Management**: Browse stored audio files and converted MIDI tracks, inspect note counts, tempo BPM, file sizes, timestamps, delete entries, and stream inline audio previews.
- **Sample Melody Generator**: Instant 1-click synthetic arpeggio melody generator to test the full pipeline immediately without requiring manual file upload.
- **Responsive Mobile & Desktop UI**: Designed with modern CSS glassmorphism, responsive grids, progress bars, and drag-and-drop zone.

## Installation & Setup

1. **Prerequisites**:
   - Python 3.10+
   - `ffmpeg` installed on system (`sudo apt install ffmpeg`)

2. **Install Python dependencies**:
   ```bash
   pip install mido numpy scipy fastapi uvicorn python-multipart pytest httpx
   ```

3. **Start the application**:
   ```bash
   uvicorn backend.app:app --host 0.0.0.0 --port 8000
   ```
   Open `http://localhost:8000` in your web browser.

## Running Tests
Run backend and end-to-end tests:
```bash
PYTHONPATH=. pytest tests/ -v
```
