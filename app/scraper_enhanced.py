import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from .models import Internship, InternshipChange, Analytics

class EnhancedInternshipScraper:
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
    
    def parse_table_of_contents(self, markdown: str) -> Dict[str, str]:
        """Parse the table of contents to extract section names and their anchor IDs.
        
        Returns:
            Dictionary mapping section names to anchor IDs
            e.g., {"Software Engineering": "-software-engineering-internship-roles"}
        """
        toc_map = {}
        lines = markdown.split('\n')
        
        # Look for the TOC section (usually has links with anchor IDs)
        for line in lines:
            # Match patterns like: 💻 **[Software Engineering](...#-software-engineering-internship-roles)**
            # Extract section name and anchor ID from markdown links
            matches = re.findall(r'\[([^\]]+)\]\([^#]*#([^)]+)\)', line)
            for section_name, anchor_id in matches:
                # Clean section name (remove emojis if any, keep just text)
                clean_name = re.sub(r'[^\w\s&,]+', '', section_name).strip()
                # Store both the full name and cleaned name
                toc_map[clean_name] = anchor_id
                toc_map[section_name] = anchor_id
        
        return toc_map
    
    def generate_anchor_from_header(self, header_text: str) -> str:
        """Generate GitHub-style anchor ID from a header.
        
        GitHub converts headers to anchors by:
        - Lowercasing
        - Replacing spaces with hyphens
        - Removing special chars/emojis
        - Removing leading/trailing hyphens
        """
        # Remove markdown header markers
        text = re.sub(r'^#+\s*', '', header_text)
        # Remove emojis and special chars, keep only alphanumeric, spaces, hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        # Lowercase and replace spaces with hyphens
        anchor = text.lower().strip().replace(' ', '-')
        # Remove multiple consecutive hyphens
        anchor = re.sub(r'-+', '-', anchor)
        # Remove leading/trailing hyphens
        anchor = anchor.strip('-')
        return anchor
    
    def extract_section(self, markdown: str, section_name: str) -> str:
        """Extract a specific section from markdown by section header name.
        
        First tries to find the section using the table of contents anchor IDs,
        then falls back to text matching.
        
        Args:
            markdown: Full markdown content
            section_name: Section name to find (e.g., "Software Engineering")
        
        Returns:
            Extracted section content (from header to next ## header), or full markdown if section not found
        """
        if not section_name:
            return markdown
        
        lines = markdown.split('\n')
        section_start = None
        section_end = None
        
        # Step 1: Parse table of contents to get anchor ID mapping
        toc_map = self.parse_table_of_contents(markdown)
        target_anchor = None
        
        # Look up the anchor ID for this section name
        section_name_lower = section_name.lower()
        for toc_name, anchor_id in toc_map.items():
            if section_name_lower in toc_name.lower() or toc_name.lower() in section_name_lower:
                target_anchor = anchor_id
                print(f"Found anchor ID '{target_anchor}' for section '{section_name}' from TOC")
                break
        
        # Step 2: Find the section header using anchor ID or text matching
        for i, line in enumerate(lines):
            if not line.strip().startswith('##'):
                continue
            
            # Method 1: Try matching by generated anchor ID
            if target_anchor:
                generated_anchor = self.generate_anchor_from_header(line)
                # Normalize both anchors (remove leading/trailing hyphens for comparison)
                normalized_target = target_anchor.strip('-').lower()
                normalized_generated = generated_anchor.strip('-').lower()
                
                # Match if they're the same or one contains the other
                if (normalized_target == normalized_generated or 
                    normalized_target.endswith(normalized_generated) or
                    normalized_generated.endswith(normalized_target)):
                    section_start = i
                    print(f"Found section '{section_name}' by anchor at line {i}: {line.strip()}")
                    print(f"  Anchor match: '{target_anchor}' -> '{generated_anchor}'")
                    break
            
            # Method 2: Fallback to text matching (case-insensitive)
            if section_start is None:
                header_lower = line.lower()
                section_name_lower = section_name.lower()
                if section_name_lower in header_lower:
                    section_start = i
                    print(f"Found section '{section_name}' by text match at line {i}: {line.strip()}")
                    break
        
        if section_start is None:
            print(f"⚠️  Section '{section_name}' not found. Available sections from TOC: {list(toc_map.keys())[:5]}")
            print(f"   Parsing entire markdown.")
            return markdown
        
        # Step 3: Find the next ## header (end of section)
        for i in range(section_start + 1, len(lines)):
            if lines[i].strip().startswith('##') and i != section_start:
                section_end = i
                break
        
        # Extract section content
        if section_end:
            section_content = '\n'.join(lines[section_start:section_end])
            print(f"✓ Extracted section '{section_name}' (lines {section_start} to {section_end})")
        else:
            section_content = '\n'.join(lines[section_start:])
            print(f"✓ Extracted section '{section_name}' (from line {section_start} to end)")
        
        return section_content
    
    def parse_markdown_table(self, markdown: str, section_filter: str = None) -> List[Dict]:
        """Parse markdown/HTML table into structured data
        
        Args:
            markdown: Full markdown content
            section_filter: Optional section name to filter (e.g., "Software Engineering")
                          Only tables within that section will be parsed
        """
        internships = []
        
        # Extract specific section if filter is provided
        if section_filter:
            markdown = self.extract_section(markdown, section_filter)
        
        # Check if it's HTML table format (from GitHub)
        if '<table>' in markdown and '<td>' in markdown:
            return self._parse_html_table(markdown)
        
        # Otherwise try markdown pipe format
        return self._parse_markdown_pipe_table(markdown)
    
    def _parse_html_table(self, markdown: str) -> List[Dict]:
        """Parse HTML table format from GitHub"""
        from bs4 import BeautifulSoup
        
        internships = []
        soup = BeautifulSoup(markdown, 'html.parser')
        
        # Find all tables
        tables = soup.find_all('table')
        print(f"Found {len(tables)} HTML table(s)")
        
        for table in tables:
            # Check if this is an internship table (has Company header)
            headers = table.find('thead')
            if headers:
                header_cells = [th.get_text(strip=True) for th in headers.find_all('th')]
                if 'Company' not in str(header_cells):
                    continue
            
            # Get all rows
            rows = table.find_all('tr')
            print(f"  Processing table with {len(rows)} rows")
            
            # Track previous company for continuation rows (↳)
            current_company = None
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 4:
                    continue
                
                try:
                    # Extract company (first cell)
                    company_cell = cells[0].get_text(strip=True)
                    
                    # Handle continuation rows (↳)
                    if company_cell == '↳' or company_cell.startswith('↳'):
                        if current_company:
                            company = current_company
                        else:
                            continue  # Skip if no previous company
                    else:
                        # Extract company name (might have links)
                        company_link = cells[0].find('a')
                        if company_link:
                            company = self.clean_text(company_link.get_text(strip=True))
                        else:
                            company = self.clean_text(company_cell)
                        current_company = company
                    
                    # Extract position (second cell) - KEEP emojis for sponsorship detection
                    position_raw = cells[1].get_text(strip=True)
                    position = self.clean_text(position_raw)
                    
                    # Extract location (third cell)
                    location = self.clean_text(cells[2].get_text(strip=True))
                    
                    # Extract application URL (fourth cell - might have images/links)
                    app_cell = cells[3]
                    app_url = ""
                    
                    # Look for Apply link - check alt text of images or link attributes
                    apply_link = None
                    for link in app_cell.find_all('a'):
                        href = link.get('href', '')
                        # Check if image has "Apply" alt text
                        img = link.find('img')
                        if img:
                            alt = img.get('alt', '').lower()
                            if 'apply' in alt:
                                apply_link = link
                                break
                        # Check href for apply
                        if 'apply' in href.lower():
                            apply_link = link
                            break
                    
                    if apply_link:
                        app_url = apply_link.get('href', '')
                    else:
                        # Fallback: get first http link (usually the Apply link)
                        for link in app_cell.find_all('a'):
                            href = link.get('href', '')
                            if href.startswith('http'):
                                app_url = href
                                break
                    
                    # Skip if no URL found or closed applications (🔒)
                    cell_text = app_cell.get_text(strip=True)
                    if not app_url or '🔒' in cell_text or app_url == '':
                        continue
                    
                    # Determine sponsorship - use RAW position text to detect emojis
                    all_cells_text = [c.get_text(strip=True) for c in cells]
                    sponsorship = self.determine_sponsorship(position_raw, location, all_cells_text)
                    
                    if company and app_url:
                        internships.append({
                            'company_name': company,
                            'position_title': position,
                            'locations': self.parse_locations(location),
                            'application_url': app_url,
                            'sponsorship_info': sponsorship
                        })
                        
                except Exception as e:
                    print(f"Error parsing HTML row: {e}")
                    continue
        
        return internships
    
    def _parse_markdown_pipe_table(self, markdown: str) -> List[Dict]:
        """Parse markdown pipe table format"""
        internships = []
        lines = markdown.split('\n')
        in_table = False
        skip_separator = False
        
        for i, line in enumerate(lines):
            # Look for table header - "| Company |" or similar
            if '|' in line and ('Company' in line or 'company' in line.lower()):
                # Check if it's actually a table header (has multiple columns)
                cells = [c.strip() for c in line.split('|') if c.strip()]
                if len(cells) >= 4:  # Company, Role, Location, Application (at minimum)
                    in_table = True
                    skip_separator = True  # Next line should be separator
                    print(f"Found markdown table header at line {i}: {line[:100]}")
                    continue
            
            # Skip separator line (|---|---|---|)
            if in_table and skip_separator and ('---' in line or all(c.strip() in ['', '-', ':'] for c in line.split('|'))):
                skip_separator = False
                continue
            
            # Parse table rows
            if in_table and '|' in line and line.strip():
                # Stop if we hit a line that doesn't start with | (end of table)
                if not line.strip().startswith('|'):
                    # Check if it's a continuation row (starts with ↳ or similar)
                    if line.strip().startswith('↳') or line.strip().startswith('| ↳'):
                        # This is a continuation row, parse it
                        pass
                    else:
                        # End of table
                        in_table = False
                        continue
                
                # Skip header/separator lines
                if 'Company' in line or '---' in line or line.strip().count('|') < 3:
                    continue
                
                # Parse cells - remove first and last empty cells from split
                cells = [cell.strip() for cell in line.split('|')]
                
                # Remove first empty cell (before first |) and last empty cell (after last |)
                if cells and not cells[0]:
                    cells = cells[1:]
                if cells and not cells[-1]:
                    cells = cells[:-1]
                
                if len(cells) >= 4:
                    try:
                        company = self.clean_text(cells[0])
                        position = self.clean_text(cells[1])
                        location = self.clean_text(cells[2])
                        app_url = self.extract_url(cells[3])
                        sponsorship = self.determine_sponsorship(position, location, cells)
                        
                        # Only add if we have both company and URL
                        if company and app_url:
                            internships.append({
                                'company_name': company,
                                'position_title': position,
                                'locations': self.parse_locations(location),
                                'application_url': app_url,
                                'sponsorship_info': sponsorship
                            })
                    except Exception as e:
                        print(f"Error parsing row at line {i}: {e}")
                        print(f"  Line: {line[:200]}")
                        continue
                elif len(cells) > 0:
                    # Might be a continuation row or special format
                    pass
        
        return internships
    
    def clean_text(self, text: str) -> str:
        """Remove markdown formatting and clean text"""
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        text = ' '.join(text.split())
        text = re.sub(r'[^\w\s\-,./&()]', '', text)
        return text.strip()
    
    def extract_url(self, cell: str) -> str:
        """Extract URL from markdown link - prefers 'Apply' links"""
        # Look for [Apply](url) first
        apply_match = re.search(r'\[Apply\]\(([^)]+)\)', cell, re.IGNORECASE)
        if apply_match:
            url = apply_match.group(1)
            if url.startswith('http'):
                return url
        
        # Fallback to any http(s) URL in parentheses
        matches = re.findall(r'\(([^)]+)\)', cell)
        for url in matches:
            if url.startswith('http'):
                return url
        
        # Last resort: look for any http(s) URL
        url_match = re.search(r'https?://[^\s\)]+', cell)
        if url_match:
            return url_match.group(0)
        
        return ""
    
    def parse_locations(self, location_str: str) -> List[str]:
        """Parse location string into list"""
        locations = []
        for loc in re.split(r'[,;|]', location_str):
            loc = loc.strip()
            if loc:
                locations.append(loc)
        return locations if locations else ["Not specified"]
    
    def determine_sponsorship(self, position: str, location: str, cells: List[str]) -> str:
        """Determine sponsorship information from text and emojis"""
        # Combine all text to check
        all_text = ' '.join([position, location] + (cells if isinstance(cells, list) else [str(cells)]))
        
        # Check for emojis first (they appear in the position/role cell)
        if '🛂' in position or '🛂' in str(cells):
            return "No sponsorship"
        if '🇺🇸' in position or '🇺🇸' in str(cells):
            return "No sponsorship"  # US Citizenship required = no sponsorship
        
        # Check text content
        text_lower = all_text.lower()
        if 'no sponsorship' in text_lower or 'us citizen' in text_lower or 'citizenship required' in text_lower:
            return "No sponsorship"
        elif 'sponsorship' in text_lower and 'no sponsorship' not in text_lower:
            return "Sponsorship available"
        else:
            return "Not specified"
    
    def detect_changes(self, db: Session, new_data: Dict, existing: Internship) -> List[str]:
        """Detect what changed in an internship"""
        changes = []
        
        if new_data['company_name'] != existing.company_name:
            changes.append('company_name')
        if new_data['position_title'] != existing.position_title:
            changes.append('position_title')
        if set(new_data.get('locations', [])) != set(existing.locations or []):
            changes.append('locations')
        if new_data['sponsorship_info'] != existing.sponsorship_info:
            changes.append('sponsorship_info')
        
        return changes
    
    def scrape_and_process(self, db: Session, section_filter: str = None) -> Tuple[List[Internship], List[Internship]]:
        """Scrape and detect new/updated internships
        
        Args:
            db: Database session
            section_filter: Optional section name to filter (e.g., "Software Engineering")
                          Only internships from that section will be scraped
        """
        start_time = time.time()
        
        filter_msg = f" (filtered to '{section_filter}')" if section_filter else ""
        print(f"Starting enhanced scrape with change detection{filter_msg}...")
        markdown = self.fetch_markdown()
        
        if not markdown:
            print("ERROR: Failed to fetch markdown from GitHub")
            self.record_analytics(db, 0, 0, False, time.time() - start_time, "Failed to fetch markdown")
            return [], []
        
        scraped_data = self.parse_markdown_table(markdown, section_filter=section_filter)
        print(f"✓ Parsed {len(scraped_data)} internships from GitHub markdown")
        
        if len(scraped_data) == 0:
            print("⚠️  WARNING: No internships parsed from markdown!")
            print("   This could mean:")
            print("   1. The GitHub markdown format changed")
            print("   2. The table header doesn't contain 'Company'")
            print("   3. All rows failed parsing (check errors above)")
            
            # Debug: check if we found the table
            lines = markdown.split('\n')
            found_header = False
            for i, line in enumerate(lines[:50]):
                if '|' in line and ('Company' in line or 'company' in line.lower()):
                    found_header = True
                    print(f"   Found potential table header at line {i}: {line[:100]}")
                    break
            
            if not found_header:
                print("   ❌ Could not find table header with 'Company' keyword")
                print(f"   First 500 chars of markdown: {markdown[:500]}")
        
        new_internships = []
        updated_internships = []
        
        # Track which URLs we've seen (to detect removed internships)
        seen_urls = set()
        
        for data in scraped_data:
            url = data['application_url']
            seen_urls.add(url)
            
            existing = db.query(Internship).filter(
                Internship.application_url == url
            ).first()
            
            if not existing:
                # NEW internship
                internship = Internship(
                    **data,
                    date_first_seen=datetime.utcnow(),
                    date_last_updated=datetime.utcnow()
                )
                db.add(internship)
                db.flush()  # Get the ID
                
                # Record change
                change = InternshipChange(
                    internship_id=internship.id,
                    change_type="created",
                    changed_fields=["all"],
                    new_values=data
                )
                db.add(change)
                
                new_internships.append(internship)
                
            else:
                # Check for UPDATES
                changed_fields = self.detect_changes(db, data, existing)
                
                if changed_fields:
                    # Store previous data
                    previous = {
                        'company_name': existing.company_name,
                        'position_title': existing.position_title,
                        'locations': existing.locations,
                        'sponsorship_info': existing.sponsorship_info
                    }
                    existing.previous_data = previous
                    
                    # Update fields
                    existing.company_name = data['company_name']
                    existing.position_title = data['position_title']
                    existing.locations = data['locations']
                    existing.sponsorship_info = data['sponsorship_info']
                    existing.date_last_updated = datetime.utcnow()
                    existing.change_count += 1
                    
                    # Record change
                    change = InternshipChange(
                        internship_id=existing.id,
                        change_type="updated",
                        changed_fields=changed_fields,
                        old_values=previous,
                        new_values=data
                    )
                    db.add(change)
                    
                    updated_internships.append(existing)
        
        # Mark internships as inactive if no longer in the list
        all_active = db.query(Internship).filter(Internship.is_active == True).all()
        removed_count = 0
        for internship in all_active:
            if internship.application_url not in seen_urls:
                internship.is_active = False
                removed_count += 1
        
        db.commit()
        
        # Record analytics
        duration = time.time() - start_time
        self.record_analytics(
            db, 
            len(new_internships), 
            len(updated_internships),
            True,
            duration,
            removed_count=removed_count
        )
        
        print(f"✓ Found {len(new_internships)} new internships")
        print(f"✓ Detected {len(updated_internships)} updated internships")
        print(f"✓ Marked {removed_count} as inactive")
        
        return new_internships, updated_internships
    
    def record_analytics(self, db: Session, new_count: int, update_count: int, 
                        success: bool, duration: float, error: str = None, removed_count: int = 0):
        """Record daily analytics"""
        today = datetime.utcnow().date()
        
        analytics = db.query(Analytics).filter(
            Analytics.date >= datetime.combine(today, datetime.min.time())
        ).first()
        
        if not analytics:
            analytics = Analytics(date=datetime.utcnow())
            db.add(analytics)
        
        analytics.internships_added = new_count
        analytics.internships_updated = update_count
        analytics.internships_removed = removed_count
        analytics.scrape_duration_seconds = duration
        analytics.scrape_success = success
        if error:
            analytics.scrape_error = error
        
        # Calculate top companies
        from sqlalchemy import func
        result = db.query(
            Internship.company_name,
            func.count(Internship.id).label('count')
        ).filter(
            Internship.is_active == True
        ).group_by(
            Internship.company_name
        ).order_by(
            func.count(Internship.id).desc()
        ).limit(10).all()
        
        analytics.top_companies = [
            {"company": row[0], "count": row[1]} 
            for row in result
        ]
        
        # Update active users count
        from .models import User
        analytics.active_users = db.query(User).filter(User.is_active == True).count()
        
        # Update emails sent (from notifications sent today)
        from .models import SentNotification
        today_start = datetime.combine(today, datetime.min.time())
        analytics.emails_sent = db.query(SentNotification).filter(
            SentNotification.sent_at >= today_start
        ).count()
        
        db.commit()

