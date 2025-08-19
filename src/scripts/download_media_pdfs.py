#!/usr/bin/env python3

import asyncio
import aiohttp
import aiofiles
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('media_pdf_download.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MediaPDFDownloader:
    def __init__(self, output_dir: str = "media_pdfs", max_concurrent: int = 5):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_concurrent = max_concurrent
        self.session = None
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.json_downloaded_count = 0
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def extract_medium_id_from_url(self, url: str) -> Optional[str]:
        """Extract medium ID from any URL format."""
        # For MediaDive URLs: https://mediadive.dsmz.de/medium/1234
        mediadive_match = re.search(r'/medium/([^/?]+)', url)
        if mediadive_match:
            return mediadive_match.group(1)
        
        # For direct PDF URLs: https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium1234.pdf
        pdf_match = re.search(r'DSMZ_Medium([^.]+)\.pdf', url)
        if pdf_match:
            return pdf_match.group(1)
        
        return None
    
    def is_direct_pdf_url(self, url: str) -> bool:
        """Check if URL is a direct PDF URL."""
        return url.endswith('.pdf') and 'dsmz.de' in url
    
    async def check_url_exists(self, url: str) -> bool:
        """Check if a URL exists without downloading the full content."""
        try:
            async with self.session.head(url) as response:
                return response.status == 200
        except:
            return False
    
    async def parse_mediadive_metadata(self, medium_url: str, html: str) -> Optional[str]:
        """Parse MediaDive HTML to extract source information from Metadata section."""
        try:
            # Look for the Metadata section and Source field
            # Pattern to find Source: followed by a link
            source_pattern = r'(?i)source[:\s]*<[^>]*href=["\']([^"\']+)["\'][^>]*>([^<]+)</[^>]*>'
            source_match = re.search(source_pattern, html)
            
            if source_match:
                source_url = source_match.group(1)
                source_text = source_match.group(2).strip()
                logger.info(f"Found source: {source_text} -> {source_url}")
                
                # Check if it's a DSMZ source
                if 'dsmz' in source_url.lower() or 'dsmz' in source_text.lower():
                    # Try to find the corresponding PDF URL
                    medium_id = self.extract_medium_id_from_url(medium_url)
                    if medium_id:
                        dsmz_pdf_url = f"https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium{medium_id}.pdf"
                        if await self.check_url_exists(dsmz_pdf_url):
                            logger.info(f"Found DSMZ PDF: {dsmz_pdf_url}")
                            return dsmz_pdf_url
                        
                        # Try alternative DSMZ PDF patterns
                        alt_patterns = [
                            f"https://www.dsmz.de/media/med{medium_id}.pdf",
                            f"https://www.dsmz.de/microorganisms/medium/pdf/medium{medium_id}.pdf"
                        ]
                        for alt_url in alt_patterns:
                            if await self.check_url_exists(alt_url):
                                logger.info(f"Found alternative DSMZ PDF: {alt_url}")
                                return alt_url
                
                # If not DSMZ, try to download from the source URL if it's a PDF
                elif source_url.endswith('.pdf'):
                    if await self.check_url_exists(source_url):
                        logger.info(f"Found non-DSMZ PDF source: {source_url}")
                        return source_url
            
            # Fallback: try direct DSMZ URL pattern
            medium_id = self.extract_medium_id_from_url(medium_url)
            if medium_id:
                dsmz_pdf_url = f"https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium{medium_id}.pdf"
                if await self.check_url_exists(dsmz_pdf_url):
                    logger.info(f"Found direct DSMZ PDF: {dsmz_pdf_url}")
                    return dsmz_pdf_url
            
        except Exception as e:
            logger.debug(f"Error parsing metadata from {medium_url}: {e}")
        
        return None

    async def download_mediadive_composition_json(self, medium_url: str) -> bool:
        """Download the molecular composition JSON for a MediaDive medium."""
        medium_id = self.extract_medium_id_from_url(medium_url)
        if not medium_id:
            return False
        
        json_url = f"https://mediadive.dsmz.de/download/composition/{medium_id}/json"
        json_filename = f"medium_{medium_id}_composition.json"
        json_filepath = self.output_dir / json_filename
        
        # Skip if already downloaded
        if json_filepath.exists():
            logger.debug(f"Skipping {json_filename} (already exists)")
            return True
        
        try:
            async with self.session.get(json_url) as response:
                if response.status != 200:
                    logger.debug(f"No composition JSON available for medium {medium_id}")
                    return False
                
                content_type = response.headers.get('content-type', '').lower()
                if 'json' not in content_type and 'application/json' not in content_type:
                    logger.debug(f"Response may not be JSON: {content_type} for {json_url}")
                
                content = await response.text()
                
                # Basic JSON validation
                try:
                    import json
                    json.loads(content)  # Validate JSON
                except json.JSONDecodeError:
                    logger.debug(f"Invalid JSON content from {json_url}")
                    return False
                
                async with aiofiles.open(json_filepath, 'w', encoding='utf-8') as f:
                    await f.write(content)
                
                logger.info(f"Downloaded: {json_filename} ({len(content)} bytes)")
                self.json_downloaded_count += 1
                return True
                
        except Exception as e:
            logger.debug(f"Error downloading composition JSON from {json_url}: {e}")
            return False

    async def get_pdf_url_from_mediadive_page(self, medium_url: str) -> Optional[str]:
        """Get PDF URL by parsing MediaDive page metadata and trying various sources."""
        medium_id = self.extract_medium_id_from_url(medium_url)
        if not medium_id:
            return None
        
        # Try to get and parse the MediaDive page
        try:
            async with self.session.get(medium_url) as response:
                if response.status != 200:
                    logger.debug(f"Failed to fetch page {medium_url}: {response.status}")
                    return None
                
                # Only try to parse if it's HTML content
                content_type = response.headers.get('content-type', '').lower()
                if 'html' not in content_type:
                    logger.debug(f"Not HTML content: {content_type}")
                    return None
                
                try:
                    # Handle encoding issues gracefully
                    html = await response.text(encoding='utf-8', errors='ignore')
                    
                    # Parse metadata to find the best PDF source
                    pdf_url = await self.parse_mediadive_metadata(medium_url, html)
                    if pdf_url:
                        return pdf_url
                    
                    # Fallback: Simple regex approach to find any PDF links
                    pdf_links = re.findall(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
                    
                    for pdf_link in pdf_links[:3]:  # Try first 3 PDF links
                        if pdf_link.startswith('http'):
                            pdf_url = pdf_link
                        elif pdf_link.startswith('/'):
                            base_url = f"{urlparse(medium_url).scheme}://{urlparse(medium_url).netloc}"
                            pdf_url = base_url + pdf_link
                        else:
                            pdf_url = urljoin(medium_url, pdf_link)
                        
                        if await self.check_url_exists(pdf_url):
                            logger.info(f"Found PDF URL from scraping: {pdf_url}")
                            return pdf_url
                            
                except (UnicodeDecodeError, Exception) as e:
                    logger.debug(f"Could not parse HTML from {medium_url}: {e}")
                    
        except Exception as e:
            logger.debug(f"Error accessing {medium_url}: {e}")
        
        # Final fallback: try direct DSMZ URL pattern
        dsmz_pdf_url = f"https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium{medium_id}.pdf"
        if await self.check_url_exists(dsmz_pdf_url):
            logger.info(f"Found fallback DSMZ PDF: {dsmz_pdf_url}")
            return dsmz_pdf_url
            
        logger.debug(f"No PDF URL found for {medium_url}")
        return None
    
    async def download_pdf(self, pdf_url: str, medium_id: str) -> bool:
        """Download PDF from URL."""
        try:
            filename = f"medium_{medium_id}.pdf"
            filepath = self.output_dir / filename
            
            # Skip if already downloaded
            if filepath.exists():
                logger.debug(f"Skipping {filename} (already exists)")
                self.skipped_count += 1
                return True
            
            async with self.session.get(pdf_url) as response:
                if response.status != 200:
                    logger.debug(f"Failed to download {pdf_url}: {response.status}")
                    self.failed_count += 1
                    return False
                
                # Check if response is actually a PDF
                content_type = response.headers.get('content-type', '').lower()
                if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
                    logger.debug(f"Response may not be PDF: {content_type} for {pdf_url}")
                
                content = await response.read()
                
                # Basic PDF validation
                if not content.startswith(b'%PDF'):
                    logger.debug(f"Downloaded content may not be a valid PDF for {pdf_url}")
                    self.failed_count += 1
                    return False
                
                async with aiofiles.open(filepath, 'wb') as f:
                    await f.write(content)
                
                logger.info(f"Downloaded: {filename} ({len(content)} bytes)")
                self.downloaded_count += 1
                return True
                
        except Exception as e:
            logger.debug(f"Error downloading PDF from {pdf_url}: {e}")
            self.failed_count += 1
            return False
    
    async def download_direct_pdf(self, pdf_url: str) -> bool:
        """Download PDF directly from URL."""
        medium_id = self.extract_medium_id_from_url(pdf_url)
        if not medium_id:
            logger.error(f"Could not extract medium ID from {pdf_url}")
            self.failed_count += 1
            return False
        
        return await self.download_pdf(pdf_url, medium_id)
    
    async def download_from_mediadive_url(self, medium_url: str) -> bool:
        """Download PDF and composition JSON from MediaDive page."""
        medium_id = self.extract_medium_id_from_url(medium_url)
        if not medium_id:
            logger.error(f"Could not extract medium ID from {medium_url}")
            self.failed_count += 1
            return False
        
        logger.info(f"Processing medium {medium_id}: {medium_url}")
        
        # Track success of both PDF and JSON downloads
        pdf_success = False
        json_success = False
        
        # Check if PDF already downloaded
        filename = f"medium_{medium_id}.pdf"
        filepath = self.output_dir / filename
        if filepath.exists():
            logger.debug(f"PDF {filename} already exists")
            pdf_success = True
            self.skipped_count += 1
        else:
            # Get PDF URL from the medium page
            pdf_url = await self.get_pdf_url_from_mediadive_page(medium_url)
            
            if pdf_url:
                # Download the PDF
                pdf_success = await self.download_pdf(pdf_url, medium_id)
            else:
                logger.debug(f"No PDF found for medium {medium_id}")
        
        # Download the molecular composition JSON
        json_success = await self.download_mediadive_composition_json(medium_url)
        
        # Consider successful if either PDF or JSON was downloaded/existed
        if pdf_success or json_success:
            return True
        else:
            self.failed_count += 1
            return False
    
    async def process_url(self, url: str) -> bool:
        """Process a single URL (either direct PDF or MediaDive URL)."""
        if self.is_direct_pdf_url(url):
            return await self.download_direct_pdf(url)
        else:
            return await self.download_from_mediadive_url(url)
    
    async def download_all_pdfs(self, url_file: str):
        """Download PDFs for all URLs in the file."""
        logger.info(f"Starting PDF download from {url_file}")
        
        # Read URLs from file
        urls = []
        try:
            with open(url_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and line.startswith('http'):
                        # Handle format with line numbers (e.g., "     1→https://...")
                        if '→' in line:
                            url = line.split('→', 1)[1].strip()
                        else:
                            url = line
                        urls.append(url)
        except Exception as e:
            logger.error(f"Error reading URL file {url_file}: {e}")
            return
        
        logger.info(f"Found {len(urls)} URLs to process")
        
        # Separate and count different URL types
        direct_pdf_urls = [url for url in urls if self.is_direct_pdf_url(url)]
        mediadive_urls = [url for url in urls if not self.is_direct_pdf_url(url)]
        
        logger.info(f"Direct PDF URLs: {len(direct_pdf_urls)}, MediaDive URLs: {len(mediadive_urls)}")
        
        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def process_with_semaphore(url):
            async with semaphore:
                await self.process_url(url)
                # Small delay to be respectful to the server
                await asyncio.sleep(0.1)
        
        # Process all URLs
        tasks = [process_with_semaphore(url) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        total_processed = self.downloaded_count + self.failed_count + self.skipped_count
        logger.info(f"Download complete. Processed: {total_processed}, PDFs: {self.downloaded_count}, JSONs: {self.json_downloaded_count}, Failed: {self.failed_count}, Skipped: {self.skipped_count}")

async def main():
    """Main function to download media PDFs."""
    url_file = "growth_media_urls__mediadive_dsmz.txt"
    
    if not Path(url_file).exists():
        logger.error(f"URL file not found: {url_file}")
        return
    
    async with MediaPDFDownloader(output_dir="media_pdfs", max_concurrent=5) as downloader:
        await downloader.download_all_pdfs(url_file)

if __name__ == "__main__":
    asyncio.run(main())