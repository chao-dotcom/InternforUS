import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict
import json

class InternshipScraper:
    def __init__(self):
        self.github_url = "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/README.md"
    
    def fetch_markdown(self) -> str:
        """Fetch the README markdown from GitHub"""
        try:
            response = requests.get(self.github_url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching markdown: {e}")
            return ""
    
    def parse_markdown_table(self, markdown: str) -> List[Dict]:
        """Parse markdown table into structured data"""
        internships = []
        
        # Split by lines and find the table
        lines = markdown.split('\n')
        in_table = False
        
        for line in lines:
            # Detect table start (line with pipes)
            if '|' in line and 'Company' in line:
                in_table = True
                continue
            
            # Skip separator line
            if in_table and '---' in line:
                continue
            
            # Parse table rows
            if in_table and '|' in line and line.strip():
                # Stop if we hit a non-table line
                if not line.startswith('|'):
                    in_table = False
                    continue
                
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                
                if len(cells) >= 4:
                    try:
                        # Extract data from cells
                        company = self.clean_text(cells[0])
                        position = self.clean_text(cells[1])
                        location = self.clean_text(cells[2])
                        
                        # Extract application URL from markdown link
                        app_url = self.extract_url(cells[3])
                        
                        # Determine sponsorship info
                        sponsorship = self.determine_sponsorship(position, location, cells)
                        
                        if company and app_url:
                            internships.append({
                                'company_name': company,
                                'position_title': position,
                                'locations': self.parse_locations(location),
                                'application_url': app_url,
                                'sponsorship_info': sponsorship,
                                'date_scraped': datetime.utcnow()
                            })
                    except Exception as e:
                        print(f"Error parsing row: {e}")
                        continue
        
        return internships
    
    def clean_text(self, text: str) -> str:
        """Remove markdown formatting and clean text"""
        # Remove markdown links but keep text
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Remove emojis and special characters
        text = re.sub(r'[^\w\s\-,./&()]', '', text)
        return text.strip()
    
    def extract_url(self, cell: str) -> str:
        """Extract URL from markdown link"""
        match = re.search(r'\(([^)]+)\)', cell)
        if match:
            url = match.group(1)
            # Handle relative URLs
            if url.startswith('http'):
                return url
        return ""
    
    def parse_locations(self, location_str: str) -> List[str]:
        """Parse location string into list"""
        locations = []
        # Split by common separators
        for loc in re.split(r'[,;|]', location_str):
            loc = loc.strip()
            if loc:
                locations.append(loc)
        return locations if locations else ["Not specified"]
    
    def determine_sponsorship(self, position: str, location: str, cells: List[str]) -> str:
        """Determine sponsorship information"""
        text = ' '.join([position, location] + cells).lower()
        
        if 'no sponsorship' in text or 'us citizen' in text or 'citizenship required' in text:
            return "No sponsorship"
        elif 'sponsorship' in text:
            return "Sponsorship available"
        else:
            return "Not specified"
    
    def scrape(self) -> List[Dict]:
        """Main scraping function"""
        print("Starting scrape...")
        markdown = self.fetch_markdown()
        
        if not markdown:
            print("Failed to fetch markdown")
            return []
        
        internships = self.parse_markdown_table(markdown)
        print(f"Scraped {len(internships)} internships")
        
        return internships

# Test the scraper
if __name__ == "__main__":
    scraper = InternshipScraper()
    results = scraper.scrape()
    
    # Print first 3 results
    for i, internship in enumerate(results[:3], 1):
        print(f"\n--- Internship {i} ---")
        print(json.dumps(internship, indent=2, default=str))

