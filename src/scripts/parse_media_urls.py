#!/usr/bin/env python3

import json
import re
import sys
from pathlib import Path
from typing import Set, List, Dict, Any

def extract_urls_from_text(text: str) -> Set[str]:
    """Extract URLs from text using regex."""
    url_pattern = r'https?://[^\s"\'<>)}\],]*'
    return set(re.findall(url_pattern, text))

def filter_media_urls(urls: Set[str]) -> Set[str]:
    """Filter URLs to include only those related to growth media."""
    media_keywords = [
        'mediadive',
        'medium',
        'media',
        'dsmz.de/microorganisms/medium',
        'catalogue/milieux',
        'fiche_milieu'
    ]
    
    media_urls = set()
    for url in urls:
        if any(keyword.lower() in url.lower() for keyword in media_keywords):
            media_urls.add(url)
    
    return media_urls

def parse_bacdive_file(filepath: str) -> Set[str]:
    """Parse BacDive strains JSON file and extract growth media URLs."""
    print(f"Processing BacDive file: {filepath}")
    
    media_urls = set()
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            # Read file in chunks to handle large files
            content = ""
            chunk_size = 1024 * 1024  # 1MB chunks
            
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                content += chunk
                
                # Extract URLs from current content
                urls = extract_urls_from_text(content)
                media_urls.update(filter_media_urls(urls))
                
                # Keep only the last part to avoid cutting URLs in half
                if len(content) > chunk_size:
                    last_url_pos = content.rfind('http')
                    if last_url_pos > chunk_size // 2:
                        content = content[last_url_pos:]
                    else:
                        content = ""
    
    except Exception as e:
        print(f"Error processing BacDive file: {e}")
        return set()
    
    return media_urls

def parse_mediadive_file(filepath: str) -> Set[str]:
    """Parse MediaDive JSON file and extract growth media URLs."""
    print(f"Processing MediaDive file: {filepath}")
    
    media_urls = set()
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Extract URLs from the data structure
        if isinstance(data, dict) and 'data' in data:
            for item in data['data']:
                if isinstance(item, dict):
                    # Check for 'link' field
                    if 'link' in item and item['link']:
                        media_urls.add(item['link'])
                    
                    # Also extract any URLs from text fields
                    for key, value in item.items():
                        if isinstance(value, str):
                            urls = extract_urls_from_text(value)
                            media_urls.update(filter_media_urls(urls))
        
        # Also extract URLs from the entire JSON as text
        json_text = json.dumps(data)
        urls = extract_urls_from_text(json_text)
        media_urls.update(filter_media_urls(urls))
    
    except Exception as e:
        print(f"Error processing MediaDive file: {e}")
        return set()
    
    return media_urls

def main():
    """Main function to parse both files and extract growth media URLs."""
    bacdive_path = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/raw/bacdive_strains.json_NEW"
    mediadive_path = "/Users/marcin/Documents/VIMSS/ontology/KG-Hub/KG-Microbe/kg-microbe/data/raw/mediadive.json"
    
    all_media_urls = set()
    
    # Parse BacDive file
    if Path(bacdive_path).exists():
        bacdive_urls = parse_bacdive_file(bacdive_path)
        all_media_urls.update(bacdive_urls)
        print(f"Found {len(bacdive_urls)} growth media URLs in BacDive file")
    else:
        print(f"BacDive file not found: {bacdive_path}")
    
    # Parse MediaDive file
    if Path(mediadive_path).exists():
        mediadive_urls = parse_mediadive_file(mediadive_path)
        all_media_urls.update(mediadive_urls)
        print(f"Found {len(mediadive_urls)} growth media URLs in MediaDive file")
    else:
        print(f"MediaDive file not found: {mediadive_path}")
    
    # Output results
    print(f"\nTotal unique growth media URLs found: {len(all_media_urls)}")
    
    # Sort URLs for consistent output
    sorted_urls = sorted(all_media_urls)
    
    # Print all URLs
    print("\nGrowth Media URLs:")
    print("=" * 50)
    for url in sorted_urls:
        print(url)
    
    # Save to file
    output_file = "growth_media_urls.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        for url in sorted_urls:
            f.write(url + '\n')
    
    print(f"\nURLs saved to: {output_file}")

if __name__ == "__main__":
    main()