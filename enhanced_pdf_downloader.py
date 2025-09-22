#!/usr/bin/env python3

import asyncio
import aiohttp
import aiofiles
import re
from pathlib import Path
from urllib.parse import urlparse, urljoin
from typing import List, Optional, Dict
import logging
import json
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhanced_pdf_download.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class EnhancedMediaDownloader:
    def __init__(self, output_dir: str = "media_pdfs", max_concurrent: int = 10):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_concurrent = max_concurrent
        self.session = None
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=60, connect=15)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    def extract_medium_id_from_url(self, url: str) -> str:
        """Extract a unique ID from any URL format."""
        parsed = urlparse(url)
        
        # DSMZ URLs: https://www.dsmz.de/microorganisms/medium/pdf/DSMZ_Medium123.pdf
        if 'dsmz.de' in parsed.netloc:
            match = re.search(r'DSMZ_Medium([^./]+)', url)
            if match:
                return f"dsmz_{match.group(1)}"
            match = re.search(r'/medium/([^/?]+)', url)
            if match:
                return f"dsmz_{match.group(1)}"
        
        # MediaDive URLs: https://mediadive.dsmz.de/medium/1234
        elif 'mediadive.dsmz.de' in parsed.netloc:
            match = re.search(r'/medium/([^/?]+)', url)
            if match:
                return f"mediadive_{match.group(1)}"
        
        # JCM URLs: https://www.jcm.riken.jp/cgi-bin/jcm/jcm_grmd?GRMD=123
        elif 'jcm.riken.jp' in parsed.netloc:
            match = re.search(r'GRMD=([^&]+)', url)
            if match:
                return f"jcm_{match.group(1)}"
        
        # CCAP URLs: https://www.ccap.ac.uk/wp-content/uploads/MR_XYZ.pdf
        elif 'ccap.ac.uk' in parsed.netloc:
            match = re.search(r'MR_([^./]+)', url)
            if match:
                return f"ccap_{match.group(1)}"
        
        # ATCC URLs: https://www.atcc.org/-/media/product-assets/documents/microbial-media-formulations/
        elif 'atcc.org' in parsed.netloc:
            match = re.search(r'atcc-medium-([^./]+)', url)
            if match:
                return f"atcc_{match.group(1)}"
            # For other ATCC URLs, use last part of path
            path_parts = parsed.path.strip('/').split('/')
            if path_parts:
                return f"atcc_{path_parts[-1].replace('.pdf', '').replace('.ashx', '')}"
        
        # Cyanosite URLs: https://www-cyanosite.bio.purdue.edu/media/table/XYZ.html
        elif 'cyanosite.bio.purdue.edu' in parsed.netloc:
            match = re.search(r'/([^./]+)\.html', url)
            if match:
                return f"cyanosite_{match.group(1)}"
        
        # Generic fallback: use domain + last path component
        domain = parsed.netloc.replace('www.', '').replace('.', '_')
        path_parts = parsed.path.strip('/').split('/')
        if path_parts and path_parts[-1]:
            filename = path_parts[-1].replace('.pdf', '').replace('.html', '').replace('.ashx', '')
            return f"{domain}_{filename}"
        
        # Ultimate fallback: hash the URL
        import hashlib
        return f"url_{hashlib.md5(url.encode()).hexdigest()[:8]}"

    async def download_file(self, url: str, output_path: Path) -> bool:
        """Download a file from URL to output path."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    # Check if it's actually a PDF or HTML
                    if 'application/pdf' in content_type or url.endswith('.pdf'):
                        # It's a PDF
                        async with aiofiles.open(output_path.with_suffix('.pdf'), 'wb') as f:
                            async for chunk in response.content.iter_chunked(8192):
                                await f.write(chunk)
                        logger.info(f"Downloaded PDF: {output_path.with_suffix('.pdf')}")
                        return True
                    elif 'text/html' in content_type or url.endswith('.html'):
                        # It's HTML, save it for text extraction
                        text = await response.text()
                        async with aiofiles.open(output_path.with_suffix('.html'), 'w', encoding='utf-8') as f:
                            await f.write(text)
                        logger.info(f"Downloaded HTML: {output_path.with_suffix('.html')}")
                        return True
                    else:
                        # Unknown content type, save anyway
                        content = await response.read()
                        async with aiofiles.open(output_path, 'wb') as f:
                            await f.write(content)
                        logger.info(f"Downloaded content: {output_path}")
                        return True
                else:
                    logger.warning(f"Failed to download {url}: HTTP {response.status}")
                    return False
        except Exception as e:
            logger.error(f"Error downloading {url}: {e}")
            return False

    async def process_url(self, url: str) -> bool:
        """Process a single URL and download the content."""
        medium_id = self.extract_medium_id_from_url(url)
        output_path = self.output_dir / f"{medium_id}"
        
        # Check if already downloaded
        if (output_path.with_suffix('.pdf').exists() or 
            output_path.with_suffix('.html').exists() or
            output_path.exists()):
            logger.debug(f"Already downloaded: {medium_id}")
            self.skipped_count += 1
            return True
        
        success = await self.download_file(url, output_path)
        if success:
            self.downloaded_count += 1
        else:
            self.failed_count += 1
        
        return success

    async def process_urls_batch(self, urls: List[str], batch_size: int = 50):
        """Process URLs in batches."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_process(url):
            async with semaphore:
                return await self.process_url(url)
        
        # Process in batches to avoid overwhelming the server
        for i in range(0, len(urls), batch_size):
            batch = urls[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}: URLs {i+1}-{min(i+batch_size, len(urls))}")
            
            tasks = [bounded_process(url) for url in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            # Progress report
            total_processed = self.downloaded_count + self.failed_count + self.skipped_count
            logger.info(f"Progress: {total_processed}/{len(urls)} URLs processed "
                       f"(Downloaded: {self.downloaded_count}, Failed: {self.failed_count}, Skipped: {self.skipped_count})")
            
            # Small delay between batches
            await asyncio.sleep(1)

async def main():
    # Read URLs from file
    urls_file = "growth_media_urls.txt"
    try:
        with open(urls_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"URLs file not found: {urls_file}")
        return
    
    logger.info(f"Found {len(urls)} URLs to process")
    
    # Start downloading
    async with EnhancedMediaDownloader() as downloader:
        await downloader.process_urls_batch(urls)
    
    logger.info(f"""
=== DOWNLOAD SUMMARY ===
Total URLs: {len(urls)}
Downloaded: {downloader.downloaded_count}
Failed: {downloader.failed_count}
Skipped: {downloader.skipped_count}
""")

if __name__ == "__main__":
    asyncio.run(main())