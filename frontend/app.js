/**
 * MidiPulse: Audio to MIDI Converter & File System Client Application
 */

document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const dropzone = document.getElementById('dropzone');
  const fileInput = document.getElementById('fileInput');
  const selectedFileInfo = document.getElementById('selectedFileInfo');
  const selectedFileName = document.getElementById('selectedFileName');
  const selectedFileSize = document.getElementById('selectedFileSize');

  const selectMode = document.getElementById('selectMode');
  const inputBpm = document.getElementById('inputBpm');
  const bpmVal = document.getElementById('bpmVal');
  const inputSensitivity = document.getElementById('inputSensitivity');
  const sensVal = document.getElementById('sensVal');
  const selectInstrument = document.getElementById('selectInstrument');

  const btnConvert = document.getElementById('btnConvert');
  const btnTryDemo = document.getElementById('btnTryDemo');
  const btnRefreshFiles = document.getElementById('btnRefreshFiles');

  const progressContainer = document.getElementById('progressContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressStatus = document.getElementById('progressStatus');

  const instantResultBanner = document.getElementById('instantResultBanner');
  const resultTitle = document.getElementById('resultTitle');
  const resultMeta = document.getElementById('resultMeta');
  const btnImmediateDownloadMidi = document.getElementById('btnImmediateDownloadMidi');
  const btnImmediateDownloadAudio = document.getElementById('btnImmediateDownloadAudio');

  const fileCardsGrid = document.getElementById('fileCardsGrid');
  const emptyState = document.getElementById('emptyState');

  const statsTotalFiles = document.getElementById('statsTotalFiles');
  const statsTotalNotes = document.getElementById('statsTotalNotes');

  const audioPlayerDock = document.getElementById('audioPlayerDock');
  const globalAudioPlayer = document.getElementById('globalAudioPlayer');
  const dockAudioTitle = document.getElementById('dockAudioTitle');
  const btnCloseDock = document.getElementById('btnCloseDock');

  let currentSelectedFile = null;

  // Formatting utilities
  function formatBytes(bytes, decimals = 1) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
  }

  // Update slider label displays
  inputBpm.addEventListener('input', (e) => {
    bpmVal.textContent = e.target.value;
  });

  inputSensitivity.addEventListener('input', (e) => {
    const val = parseFloat(e.target.value);
    let label = 'Medium';
    if (val <= 0.3) label = 'Strict';
    else if (val >= 0.7) label = 'High';
    sensVal.textContent = `${label} (${val.toFixed(2)})`;
  });

  // Dropzone drag-and-drop & file selection
  dropzone.addEventListener('click', () => {
    fileInput.click();
  });

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add('dragover');
    }, false);
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove('dragover');
    }, false);
  });

  dropzone.addEventListener('drop', (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      handleSelectedFile(files[0]);
    }
  });

  fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleSelectedFile(e.target.files[0]);
    }
  });

  function handleSelectedFile(file) {
    currentSelectedFile = file;
    selectedFileName.textContent = file.name;
    selectedFileSize.textContent = formatBytes(file.size);
    selectedFileInfo.style.display = 'inline-flex';
    btnConvert.disabled = false;
    btnConvert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // Instant trigger helper for downloads (Mobile & PC)
  function triggerImmediateDownload(url, filename) {
    const a = document.createElement('a');
    a.href = url;
    a.setAttribute('download', filename || '');
    a.target = '_blank';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // Convert File API
  btnConvert.addEventListener('click', async () => {
    if (!currentSelectedFile) return;

    btnConvert.disabled = true;
    instantResultBanner.style.display = 'none';
    progressContainer.style.display = 'block';
    progressBarFill.style.width = '20%';
    progressStatus.textContent = 'Uploading audio file...';

    const formData = new FormData();
    formData.append('file', currentSelectedFile);
    formData.append('bpm', inputBpm.value);
    formData.append('sensitivity', inputSensitivity.value);
    formData.append('mode', selectMode.value);
    formData.append('instrument', selectInstrument.value);

    let progressTimer = setInterval(() => {
      const currentW = parseInt(progressBarFill.style.width) || 20;
      if (currentW < 85) {
        progressBarFill.style.width = (currentW + 15) + '%';
        if (currentW > 40) progressStatus.textContent = 'FFmpeg decoding & spectrogram analysis...';
        if (currentW > 70) progressStatus.textContent = 'Polyphonic note tracking & MIDI generation...';
      }
    }, 400);

    try {
      const response = await fetch('/api/convert', {
        method: 'POST',
        body: formData
      });

      clearInterval(progressTimer);

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Conversion failed');
      }

      const data = await response.json();
      progressBarFill.style.width = '100%';
      progressStatus.textContent = 'Complete! MIDI file ready.';

      displayConversionSuccess(data);
      loadFiles();
      loadStats();

      // Trigger immediate download automatically for user convenience
      setTimeout(() => {
        triggerImmediateDownload(data.download_url, `${data.file.stem_name}.mid`);
      }, 500);

    } catch (err) {
      clearInterval(progressTimer);
      progressBarFill.style.width = '100%';
      progressBarFill.style.background = '#ef4444';
      progressStatus.textContent = 'Error: ' + err.message;
      alert('Error during conversion: ' + err.message);
    } finally {
      btnConvert.disabled = false;
    }
  });

  // Demo Melody Generator
  btnTryDemo.addEventListener('click', async () => {
    btnTryDemo.disabled = true;
    instantResultBanner.style.display = 'none';
    progressContainer.style.display = 'block';
    progressBarFill.style.width = '30%';
    progressBarFill.style.background = 'var(--accent-gradient)';
    progressStatus.textContent = 'Synthesizing demo arpeggio melody...';

    const formData = new FormData();
    formData.append('mode', selectMode.value);
    formData.append('bpm', inputBpm.value);

    try {
      progressBarFill.style.width = '70%';
      progressStatus.textContent = 'Transcribing arpeggio into MIDI notes...';

      const response = await fetch('/api/generate-demo', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error('Failed to generate demo');
      }

      const data = await response.json();
      progressBarFill.style.width = '100%';
      progressStatus.textContent = 'Demo melody synthesized and transcribed!';

      displayConversionSuccess(data);
      loadFiles();
      loadStats();

      // Trigger instant download
      setTimeout(() => {
        triggerImmediateDownload(data.download_url, `${data.file.stem_name}.mid`);
      }, 500);

    } catch (err) {
      alert('Error generating demo: ' + err.message);
    } finally {
      btnTryDemo.disabled = false;
    }
  });

  function displayConversionSuccess(data) {
    const file = data.file;
    resultTitle.textContent = `Converted "${file.original_name}"`;
    resultMeta.textContent = `${file.notes_count} notes transcribed • Duration: ${file.duration_sec}s • MIDI Size: ${file.midi_size_formatted}`;

    btnImmediateDownloadMidi.href = data.download_url;
    btnImmediateDownloadMidi.download = `${file.stem_name}.mid`;

    btnImmediateDownloadAudio.href = data.audio_url;
    btnImmediateDownloadAudio.download = file.original_name;

    instantResultBanner.style.display = 'flex';
    instantResultBanner.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // File System Table / Cards Loading
  async function loadFiles() {
    try {
      const res = await fetch('/api/files');
      const data = await res.json();
      const files = data.files || [];

      if (files.length === 0) {
        emptyState.style.display = 'block';
        fileCardsGrid.innerHTML = '';
        return;
      }

      emptyState.style.display = 'none';
      fileCardsGrid.innerHTML = '';

      files.forEach(file => {
        const card = document.createElement('div');
        card.className = 'file-card';
        card.innerHTML = `
          <div class="file-card-top">
            <h4 class="file-card-title">${escapeHtml(file.original_name)}</h4>
            <span class="file-card-badge">${escapeHtml(file.mode || 'polyphonic')}</span>
          </div>

          <div class="file-card-meta">
            <span class="meta-item">Notes: <strong>${file.notes_count}</strong></span>
            <span class="meta-item">BPM: <strong>${file.bpm}</strong></span>
            <span class="meta-item">Audio: <strong>${file.audio_size_formatted}</strong></span>
            <span class="meta-item">MIDI: <strong>${file.midi_size_formatted}</strong></span>
            <span class="meta-item">${file.created_at_formatted}</span>
          </div>

          <div class="file-card-actions">
            <button class="btn-play-audio" data-id="${file.id}" data-name="${escapeHtml(file.original_name)}">
              <svg viewBox="0 0 24 24" width="14" height="14" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
              </svg>
              Preview
            </button>

            <div class="download-btn-group">
              <a href="/api/files/${file.id}/download/midi" download="${escapeHtml(file.stem_name)}.mid" class="btn-download-midi" title="Instant Download MIDI">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.5">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="7 10 12 15 17 10"></polyline>
                  <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                MIDI
              </a>
              <button class="btn-icon btn-delete" data-id="${file.id}" title="Delete File">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </button>
            </div>
          </div>
        `;
        fileCardsGrid.appendChild(card);
      });

      // Bind Preview Buttons
      document.querySelectorAll('.btn-play-audio').forEach(btn => {
        btn.addEventListener('click', () => {
          const fileId = btn.getAttribute('data-id');
          const fileName = btn.getAttribute('data-name');
          playAudioPreview(fileId, fileName);
        });
      });

      // Bind Delete Buttons
      document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', async () => {
          const fileId = btn.getAttribute('data-id');
          if (confirm('Are you sure you want to delete this file from the system?')) {
            await deleteFile(fileId);
          }
        });
      });

    } catch (e) {
      console.error('Failed to load files:', e);
    }
  }

  // Audio preview player
  function playAudioPreview(fileId, fileName) {
    dockAudioTitle.textContent = fileName;
    globalAudioPlayer.src = `/api/files/${fileId}/stream-audio`;
    audioPlayerDock.style.display = 'block';
    globalAudioPlayer.play().catch(e => console.log('Autoplay deferred:', e));
  }

  btnCloseDock.addEventListener('click', () => {
    globalAudioPlayer.pause();
    audioPlayerDock.style.display = 'none';
  });

  // Delete File API
  async function deleteFile(fileId) {
    try {
      const res = await fetch(`/api/files/${fileId}`, { method: 'DELETE' });
      if (res.ok) {
        loadFiles();
        loadStats();
      }
    } catch (e) {
      alert('Failed to delete file');
    }
  }

  // Stats Loading
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const stats = await res.json();
      statsTotalFiles.textContent = stats.total_files || 0;
      statsTotalNotes.textContent = stats.total_notes_converted || 0;
    } catch (e) {
      console.error(e);
    }
  }

  btnRefreshFiles.addEventListener('click', () => {
    loadFiles();
    loadStats();
  });

  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Initialize data on load
  loadFiles();
  loadStats();
});
