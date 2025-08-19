#!/usr/bin/env python3

import os
import logging
from pathlib import Path
from typing import List, Optional
import asyncio
import aiofiles
from markitdown import MarkItDown

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('pdf_conversion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PDFToTextConverter:
    def __init__(self, pdf_dir: str = "media_pdfs", output_dir: str = "media_texts", max_concurrent: int = 3):
        self.pdf_dir = Path(pdf_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_concurrent = max_concurrent
        self.markitdown = MarkItDown()
        self.converted_count = 0
        self.failed_count = 0
        self.skipped_count = 0
    
    def get_pdf_files(self) -> List[Path]:
        """Get all PDF files in the PDF directory."""
        pdf_files = list(self.pdf_dir.glob("*.pdf"))
        logger.info(f"Found {len(pdf_files)} PDF files to convert")
        return pdf_files
    
    def get_output_filename(self, pdf_path: Path) -> Path:
        """Get the output text filename for a PDF file."""
        return self.output_dir / f"{pdf_path.stem}.md"
    
    async def convert_pdf_to_text(self, pdf_path: Path) -> bool:
        """Convert a single PDF to text using markitdown."""
        output_path = self.get_output_filename(pdf_path)
        
        # Skip if already converted
        if output_path.exists():
            logger.info(f"Skipping {pdf_path.name} (already converted)")
            self.skipped_count += 1
            return True
        
        try:
            logger.info(f"Converting {pdf_path.name} to text...")
            
            # Convert PDF to markdown using MarkItDown
            result = self.markitdown.convert(str(pdf_path))
            
            if result and result.text_content:
                # Write the converted text to file
                async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                    await f.write(result.text_content)
                
                logger.info(f"Successfully converted {pdf_path.name} -> {output_path.name}")
                self.converted_count += 1
                return True
            else:
                logger.warning(f"No text content extracted from {pdf_path.name}")
                self.failed_count += 1
                return False
                
        except Exception as e:
            logger.error(f"Error converting {pdf_path.name}: {e}")
            self.failed_count += 1
            return False
    
    async def convert_all_pdfs(self):
        """Convert all PDFs to text format."""
        pdf_files = self.get_pdf_files()
        
        if not pdf_files:
            logger.warning("No PDF files found to convert")
            return
        
        logger.info(f"Starting conversion of {len(pdf_files)} PDFs...")
        
        # Create semaphore to limit concurrent conversions
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def convert_with_semaphore(pdf_path):
            async with semaphore:
                await self.convert_pdf_to_text(pdf_path)
        
        # Process PDFs concurrently
        tasks = [convert_with_semaphore(pdf_path) for pdf_path in pdf_files]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Conversion complete. Success: {self.converted_count}, Failed: {self.failed_count}, Skipped: {self.skipped_count}")
    
    def create_summary_report(self):
        """Create a summary report of the conversion process."""
        report_path = self.output_dir / "conversion_summary.md"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("# PDF to Text Conversion Summary\n\n")
                f.write(f"**Total PDFs processed:** {self.converted_count + self.failed_count + self.skipped_count}\n")
                f.write(f"**Successfully converted:** {self.converted_count}\n")
                f.write(f"**Failed conversions:** {self.failed_count}\n")
                f.write(f"**Skipped (already converted):** {self.skipped_count}\n\n")
                
                f.write("## Converted Files\n\n")
                text_files = list(self.output_dir.glob("*.md"))
                text_files = [f for f in text_files if f.name != "conversion_summary.md"]
                
                for text_file in sorted(text_files):
                    f.write(f"- [{text_file.name}](./{text_file.name})\n")
            
            logger.info(f"Summary report created: {report_path}")
            
        except Exception as e:
            logger.error(f"Error creating summary report: {e}")

async def main():
    """Main function to convert PDFs to text."""
    converter = PDFToTextConverter(
        pdf_dir="media_pdfs",
        output_dir="media_texts",
        max_concurrent=3
    )
    
    await converter.convert_all_pdfs()
    converter.create_summary_report()

if __name__ == "__main__":
    asyncio.run(main())