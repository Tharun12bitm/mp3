"""End-to-end browser test for full-stack user conversion and download flows."""

import time
import pytest
from playwright.sync_api import sync_playwright

def test_full_user_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto("http://localhost:8000")

        # Check page header
        assert page.title() == "Audio to MIDI Studio | Convert MP3 to MIDI & Immediate Download"
        header_text = page.locator(".logo-title").text_content()
        assert "MidiPulse" in header_text

        # Click Try Sample Demo button
        demo_btn = page.locator("#btnTryDemo")
        demo_btn.click()

        # Wait for conversion banner
        page.wait_for_selector("#instantResultBanner:visible", timeout=15000)
        banner_text = page.locator("#resultTitle").text_content()
        assert "Converted" in banner_text

        # Verify immediate download MIDI button exists and has correct attributes
        midi_download = page.locator("#btnImmediateDownloadMidi")
        assert midi_download.is_visible()
        download_attr = midi_download.get_attribute("download")
        assert download_attr.endswith(".mid")

        # Verify file appears in file system explorer table
        cards = page.locator(".file-card")
        assert cards.count() >= 1

        browser.close()
