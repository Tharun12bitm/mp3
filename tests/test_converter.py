"""Unit tests for the Audio to MIDI converter algorithms."""

import pytest
import numpy as np
from pathlib import Path
import mido

from backend.converter import (
    hz_to_midi,
    midi_to_hz,
    note_name,
    detect_notes_polyphonic,
    create_midi_file,
    convert_audio_to_midi,
    generate_demo_audio
)

def test_pitch_conversions():
    # A4 is 440Hz -> MIDI 69
    assert hz_to_midi(440.0) == 69
    assert round(midi_to_hz(69), 1) == 440.0
    assert note_name(69) == "A4"

    # Middle C (C4) is ~261.63Hz -> MIDI 60
    assert hz_to_midi(261.63) == 60
    assert note_name(60) == "C4"

def test_detect_notes_synthetic_melody():
    sr = 22050
    duration = 0.5
    # Generate C4 (261.63 Hz) followed by E4 (329.63 Hz)
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    tone1 = 0.8 * np.sin(2 * np.pi * 261.63 * t)
    tone2 = 0.8 * np.sin(2 * np.pi * 329.63 * t)
    audio = np.concatenate([tone1, tone2])

    notes = detect_notes_polyphonic(audio, sample_rate=sr, sensitivity=0.5, mode="melody")
    assert len(notes) >= 2
    detected_pitches = [n["pitch"] for n in notes]
    assert 60 in detected_pitches  # C4
    assert 64 in detected_pitches  # E4

def test_create_midi_file(tmp_path):
    midi_path = tmp_path / "output.mid"
    notes = [
        {"pitch": 60, "name": "C4", "start": 0.0, "end": 0.5, "velocity": 100},
        {"pitch": 64, "name": "E4", "start": 0.5, "end": 1.0, "velocity": 100},
    ]
    create_midi_file(notes, midi_path, bpm=120)
    assert midi_path.exists()
    assert midi_path.stat().st_size > 0

    mid = mido.MidiFile(str(midi_path))
    assert len(mid.tracks) == 1
    events = [m for m in mid.tracks[0] if m.type in ('note_on', 'note_off')]
    assert len(events) == 4

def test_empty_audio_handling(tmp_path):
    midi_path = tmp_path / "empty.mid"
    create_midi_file([], midi_path)
    assert midi_path.exists()
    mid = mido.MidiFile(str(midi_path))
    assert len(mid.tracks) == 1
