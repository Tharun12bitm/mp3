"""Audio to MIDI converter engine using ffmpeg, scipy, and mido."""

import subprocess
import tempfile
import numpy as np
import scipy.io.wavfile as wavfile
import scipy.signal
import mido
from mido import Message, MidiFile, MidiTrack, MetaMessage
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

A4_FREQ = 440.0
A4_MIDI = 69

def hz_to_midi(hz: float) -> int:
    """Convert frequency in Hertz to closest MIDI note number (0-127)."""
    if hz <= 0:
        return 0
    midi = round(69 + 12 * np.log2(hz / 440.0))
    return int(np.clip(midi, 21, 108))  # Standard 88-key piano range (A0 to C8)

def midi_to_hz(midi_note: int) -> float:
    """Convert MIDI note number to frequency in Hertz."""
    return 440.0 * (2.0 ** ((midi_note - 69) / 12.0))

def note_name(midi_note: int) -> str:
    """Return friendly note name (e.g., C4, F#5)."""
    names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    octave = (midi_note // 12) - 1
    name = names[midi_note % 12]
    return f"{name}{octave}"

def decode_audio_to_wav(input_path: Path, output_wav_path: Path, sample_rate: int = 22050) -> None:
    """Convert any audio file (MP3, WAV, OGG, AAC, FLAC, etc.) to mono WAV using ffmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-ac", "1",               # Mono
        "-ar", str(sample_rate),  # Resample to consistent sample rate
        "-f", "wav",
        str(output_wav_path)
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed to decode audio: {result.stderr.decode('utf-8', errors='ignore')}")

def detect_notes_polyphonic(
    audio: np.ndarray,
    sample_rate: int,
    sensitivity: float = 0.5,
    min_note_duration: float = 0.08,
    hop_length: int = 512,
    n_fft: int = 2048,
    mode: str = "polyphonic"
) -> List[Dict[str, Any]]:
    """Detect musical notes from raw audio waveform using Short-Time Fourier Transform (STFT).

    Supports 'polyphonic', 'melody' (monophonic lead), and 'bass'.
    Returns list of notes: [{'pitch': int, 'name': str, 'start': float, 'end': float, 'velocity': int}]
    """
    if len(audio) == 0:
        return []

    # Normalize audio
    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val
    else:
        return []

    # Compute STFT
    frequencies, times, zxx = scipy.signal.stft(
        audio,
        fs=sample_rate,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        window='hann'
    )
    magnitude = np.abs(zxx)

    # Frequency mask (limit to musical range 27.5 Hz to ~4200 Hz)
    freq_min = 27.5
    freq_max = 4200.0
    if mode == "bass":
        freq_max = 300.0
    elif mode == "melody":
        freq_min = 65.0
        freq_max = 2100.0

    valid_freq_mask = (frequencies >= freq_min) & (frequencies <= freq_max)
    sub_freqs = frequencies[valid_freq_mask]
    sub_mag = magnitude[valid_freq_mask, :]

    if sub_mag.size == 0 or np.max(sub_mag) == 0:
        return []

    sub_mag = sub_mag / np.max(sub_mag)

    # Energy threshold based on sensitivity (0.1 to 1.0)
    # Higher sensitivity means lower threshold (detects more notes)
    # Sensitivity: 0.1 (strict, high thresh) -> 1.0 (sensitive, low thresh)
    threshold = (1.1 - np.clip(sensitivity, 0.1, 1.0)) * 0.15

    # Track active notes across time frames
    # Active notes dict: {pitch: {'start_time': float, 'last_seen': float, 'max_amp': float}}
    active_notes: Dict[int, Dict[str, float]] = {}
    completed_notes: List[Dict[str, Any]] = []

    for frame_idx, t in enumerate(times):
        frame_spectrum = sub_mag[:, frame_idx]

        # Find spectral peaks
        peaks, properties = scipy.signal.find_peaks(
            frame_spectrum,
            height=threshold,
            distance=3
        )

        current_frame_pitches = {}
        if len(peaks) > 0:
            peak_freqs = sub_freqs[peaks]
            peak_amps = frame_spectrum[peaks]

            if mode == "melody":
                # Only take the strongest dominant peak in melody mode
                best_idx = np.argmax(peak_amps)
                pitch = hz_to_midi(peak_freqs[best_idx])
                current_frame_pitches[pitch] = peak_amps[best_idx]
            else:
                # Polyphonic mode: allow top N peaks
                sorted_peak_indices = np.argsort(peak_amps)[::-1]
                max_peaks = 6 if mode == "polyphonic" else 2
                for p_idx in sorted_peak_indices[:max_peaks]:
                    p_freq = peak_freqs[p_idx]
                    p_amp = peak_amps[p_idx]
                    pitch = hz_to_midi(p_freq)
                    if pitch not in current_frame_pitches or current_frame_pitches[pitch] < p_amp:
                        current_frame_pitches[pitch] = p_amp

        # Update or end notes
        time_step = hop_length / sample_rate
        # Check active notes not present in current frame
        ended_pitches = []
        for pitch, note_data in active_notes.items():
            if pitch in current_frame_pitches:
                note_data['last_seen'] = t
                note_data['max_amp'] = max(note_data['max_amp'], current_frame_pitches[pitch])
            else:
                # Gap tolerance: if missing for more than ~0.06s, close note
                if t - note_data['last_seen'] > 0.06:
                    ended_pitches.append(pitch)

        for pitch in ended_pitches:
            note_data = active_notes.pop(pitch)
            duration = note_data['last_seen'] - note_data['start_time']
            if duration >= min_note_duration:
                vel = int(np.clip(note_data['max_amp'] * 127 * 1.5, 40, 127))
                completed_notes.append({
                    'pitch': pitch,
                    'name': note_name(pitch),
                    'start': round(note_data['start_time'], 3),
                    'end': round(note_data['last_seen'] + time_step, 3),
                    'duration': round(duration + time_step, 3),
                    'velocity': vel
                })

        # Add newly detected pitches
        for pitch, amp in current_frame_pitches.items():
            if pitch not in active_notes:
                active_notes[pitch] = {
                    'start_time': t,
                    'last_seen': t,
                    'max_amp': amp
                }

    # Flush remaining active notes at the end
    end_time = times[-1] if len(times) > 0 else 0
    time_step = hop_length / sample_rate
    for pitch, note_data in active_notes.items():
        duration = end_time - note_data['start_time']
        if duration >= min_note_duration:
            vel = int(np.clip(note_data['max_amp'] * 127 * 1.5, 40, 127))
            completed_notes.append({
                'pitch': pitch,
                'name': note_name(pitch),
                'start': round(note_data['start_time'], 3),
                'end': round(end_time + time_step, 3),
                'duration': round(duration + time_step, 3),
                'velocity': vel
            })

    # Sort notes chronologically
    completed_notes.sort(key=lambda x: (x['start'], x['pitch']))
    return completed_notes

def create_midi_file(
    notes: List[Dict[str, Any]],
    output_midi_path: Path,
    bpm: int = 120,
    instrument: int = 0  # Acoustic Grand Piano
) -> None:
    """Convert detected notes into a standard MIDI (.mid) file."""
    mid = MidiFile(type=0, ticks_per_beat=480)
    track = MidiTrack()
    mid.tracks.append(track)

    # Add tempo and instrument
    tempo = mido.bpm2tempo(bpm)
    track.append(MetaMessage('set_tempo', tempo=tempo, time=0))
    track.append(MetaMessage('track_name', name='Converted Audio Track', time=0))
    track.append(Message('program_change', program=instrument, time=0))

    if not notes:
        mid.save(str(output_midi_path))
        return

    # Convert notes to chronological list of events (note_on / note_off)
    events: List[Tuple[float, str, int, int]] = []
    for n in notes:
        events.append((n['start'], 'note_on', n['pitch'], n['velocity']))
        events.append((n['end'], 'note_off', n['pitch'], 0))

    # Sort events by timestamp
    events.sort(key=lambda x: (x[0], 0 if x[1] == 'note_off' else 1))

    # Convert seconds to MIDI ticks
    seconds_per_tick = (60.0 / bpm) / mid.ticks_per_beat
    last_tick = 0

    for timestamp, event_type, pitch, velocity in events:
        current_tick = int(round(timestamp / seconds_per_tick))
        delta_ticks = max(0, current_tick - last_tick)
        last_tick = current_tick

        if event_type == 'note_on':
            track.append(Message('note_on', note=pitch, velocity=velocity, time=delta_ticks))
        else:
            track.append(Message('note_off', note=pitch, velocity=0, time=delta_ticks))

    track.append(MetaMessage('end_of_track', time=120))
    mid.save(str(output_midi_path))

def convert_audio_to_midi(
    input_audio_path: Path,
    output_midi_path: Path,
    bpm: int = 120,
    sensitivity: float = 0.5,
    mode: str = "polyphonic",
    instrument: int = 0
) -> Dict[str, Any]:
    """Complete pipeline: input audio (MP3/WAV/etc.) -> decode -> note detection -> MIDI file."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        tmp_wav_path = Path(tmp_wav.name)

    try:
        sample_rate = 22050
        decode_audio_to_wav(input_audio_path, tmp_wav_path, sample_rate=sample_rate)
        sr, audio_data = wavfile.read(str(tmp_wav_path))

        # Handle stereo or int formats
        if audio_data.ndim > 1:
            audio_data = np.mean(audio_data, axis=1)
        if audio_data.dtype != np.float32 and audio_data.dtype != np.float64:
            audio_data = audio_data.astype(np.float32)

        notes = detect_notes_polyphonic(
            audio_data,
            sample_rate=sr,
            sensitivity=sensitivity,
            mode=mode
        )

        create_midi_file(notes, output_midi_path, bpm=bpm, instrument=instrument)

        duration_sec = len(audio_data) / sr if sr > 0 else 0
        return {
            "success": True,
            "notes_count": len(notes),
            "duration_sec": round(duration_sec, 2),
            "bpm": bpm,
            "mode": mode,
            "notes_sample": notes[:10]  # First 10 notes for preview
        }
    finally:
        if tmp_wav_path.exists():
            tmp_wav_path.unlink()

def generate_demo_audio(output_mp3_path: Path) -> Path:
    """Generate a high-quality test melody audio file (MP3) for immediate testing without upload."""
    sample_rate = 44100
    # Simple C Major arpeggio melody: C4, E4, G4, B4, C5, G4, E4, C4
    melody = [
        (60, 0.4),  # C4
        (64, 0.4),  # E4
        (67, 0.4),  # G4
        (71, 0.4),  # B4
        (72, 0.6),  # C5
        (67, 0.4),  # G4
        (64, 0.4),  # E4
        (60, 0.8),  # C4
    ]

    total_samples = int(sum(dur for _, dur in melody) * sample_rate)
    audio = np.zeros(total_samples, dtype=np.float32)

    current_sample = 0
    for pitch, duration in melody:
        freq = midi_to_hz(pitch)
        num_samples = int(duration * sample_rate)
        t = np.linspace(0, duration, num_samples, endpoint=False)
        # Fundamental + harmonic overtones with ADSR envelope
        tone = (
            0.6 * np.sin(2 * np.pi * freq * t) +
            0.25 * np.sin(2 * np.pi * 2 * freq * t) +
            0.15 * np.sin(2 * np.pi * 3 * freq * t)
        )
        # Envelope: Attack, Decay to Sustain, Release
        env = np.ones(num_samples)
        attack_len = int(0.05 * sample_rate)
        release_len = int(0.1 * sample_rate)
        if attack_len < num_samples:
            env[:attack_len] = np.linspace(0, 1, attack_len)
        if release_len < num_samples:
            env[-release_len:] = np.linspace(1, 0, release_len)

        audio[current_sample:current_sample + num_samples] += tone * env
        current_sample += num_samples

    # Normalize to 16-bit PCM WAV first, then ffmpeg to MP3
    audio = audio / np.max(np.abs(audio)) * 0.9
    int16_audio = (audio * 32767).astype(np.int16)

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        wav_path = Path(tmp_wav.name)
        wavfile.write(str(wav_path), sample_rate, int16_audio)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(wav_path),
        "-b:a", "192k",
        str(output_mp3_path)
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    if wav_path.exists():
        wav_path.unlink()

    return output_mp3_path
