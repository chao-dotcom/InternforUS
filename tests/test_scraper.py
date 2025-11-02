"""Tests for the scraper module"""
import pytest
from app.scraper import InternshipScraper

def test_scraper_initialization():
    """Test that scraper initializes correctly"""
    scraper = InternshipScraper()
    assert scraper.github_url == "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"

def test_fetch_markdown():
    """Test fetching markdown from GitHub"""
    scraper = InternshipScraper()
    markdown = scraper.fetch_markdown()
    assert markdown is not None
    assert len(markdown) > 0
    assert "Company" in markdown or "internship" in markdown.lower()

def test_parse_markdown_table():
    """Test parsing markdown table"""
    scraper = InternshipScraper()
    # Sample markdown table
    sample_markdown = """
# Internships

| Company | Position | Location | Link |
|---------|----------|----------|------|
| Google | Software Engineer | Remote | [Apply](https://google.com) |
| Microsoft | Data Scientist | Seattle | [Apply](https://microsoft.com) |
"""
    results = scraper.parse_markdown_table(sample_markdown)
    assert len(results) > 0

def test_clean_text():
    """Test text cleaning function"""
    scraper = InternshipScraper()
    dirty_text = "[Software Engineer](https://example.com) 🔥"
    clean = scraper.clean_text(dirty_text)
    assert "Software Engineer" in clean
    assert "🔥" not in clean
    assert "https" not in clean

def test_extract_url():
    """Test URL extraction from markdown"""
    scraper = InternshipScraper()
    markdown_link = "[Apply](https://example.com/apply)"
    url = scraper.extract_url(markdown_link)
    assert url == "https://example.com/apply"

def test_parse_locations():
    """Test location parsing"""
    scraper = InternshipScraper()
    location_str = "New York, San Francisco, Remote"
    locations = scraper.parse_locations(location_str)
    assert len(locations) == 3
    assert "New York" in locations

def test_scrape_integration():
    """Integration test for full scrape"""
    scraper = InternshipScraper()
    results = scraper.scrape()
    # Should return a list (even if empty)
    assert isinstance(results, list)

