#!/usr/bin/env python3

import json
import asyncio
import aiofiles
from pathlib import Path
from typing import Dict, Any, List, Union
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('json_conversion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class JSONToMarkdownConverter:
    def __init__(self, input_dir: str = "media_pdfs", output_dir: str = "media_compositions", max_concurrent: int = 10):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.max_concurrent = max_concurrent
        self.converted_count = 0
        self.failed_count = 0
        self.skipped_count = 0
    
    def get_json_files(self) -> List[Path]:
        """Get all JSON composition files."""
        json_files = list(self.input_dir.glob("*_composition.json"))
        logger.info(f"Found {len(json_files)} JSON composition files to convert")
        return json_files
    
    def get_output_filename(self, json_path: Path) -> Path:
        """Get the output markdown filename for a JSON file."""
        # Convert medium_123_composition.json to medium_123_composition.md
        return self.output_dir / f"{json_path.stem}.md"
    
    def format_composition_data(self, data: Any) -> str:
        """Format JSON composition data as markdown."""
        md_content = []
        
        # Handle both list and dict formats
        if isinstance(data, list):
            # Data is a list of compounds
            if not data:
                return "# Empty Composition Data\n\n*No composition data available*\n"
            
            # Extract medium ID from first item
            medium_id = data[0].get('medium_id', 'Unknown') if data and isinstance(data[0], dict) else 'Unknown'
            medium_name = f"Medium {medium_id}"
            
            # Header
            md_content.append(f"# {medium_name} - Molecular Composition\n\n")
            
            # Components table
            md_content.append("## Components\n\n")
            md_content.append("| Compound | g/L | mmol/L | Optional |\n")
            md_content.append("|----------|-----|---------|----------|\n")
            
            for component in data:
                if isinstance(component, dict):
                    compound = component.get('compound', 'Unknown')
                    g_l = component.get('g_l', '')
                    mmol_l = component.get('mmol_l', '')
                    optional = component.get('optional', '')
                    md_content.append(f"| {compound} | {g_l} | {mmol_l} | {optional} |\n")
            
            md_content.append("\n")
            
        elif isinstance(data, dict):
            # Data is a dictionary object
            # Extract medium ID from the data
            medium_id = data.get('medium_id', 'Unknown')
            medium_name = data.get('name', f'Medium {medium_id}')
            
            # Header
            md_content.append(f"# {medium_name} - Molecular Composition\n\n")
            
            # Basic information
            if 'description' in data:
                md_content.append(f"**Description:** {data['description']}\n\n")
            
            if 'source' in data:
                md_content.append(f"**Source:** {data['source']}\n\n")
            
            if 'reference' in data:
                md_content.append(f"**Reference:** {data['reference']}\n\n")
            
            if 'pH' in data:
                if isinstance(data['pH'], dict):
                    ph_min = data['pH'].get('min', '')
                    ph_max = data['pH'].get('max', '')
                    if ph_min and ph_max:
                        md_content.append(f"**pH Range:** {ph_min} - {ph_max}\n\n")
                    elif ph_min:
                        md_content.append(f"**pH:** {ph_min}\n\n")
                else:
                    md_content.append(f"**pH:** {data['pH']}\n\n")
            
            # Components section
            if 'components' in data:
                md_content.append("## Components\n\n")
                components = data['components']
                
                if isinstance(components, list):
                    # Handle list of components
                    md_content.append("| Component | Amount | Unit | Optional |\n")
                    md_content.append("|-----------|--------|------|----------|\n")
                    
                    for component in components:
                        if isinstance(component, dict):
                            name = component.get('name', component.get('compound', 'Unknown'))
                            amount = component.get('amount', component.get('g_l', ''))
                            unit = component.get('unit', 'g/L')
                            optional = component.get('optional', '')
                            md_content.append(f"| {name} | {amount} | {unit} | {optional} |\n")
                        else:
                            md_content.append(f"| {component} | | | |\n")
                            
                elif isinstance(components, dict):
                    # Handle dictionary of components
                    md_content.append("| Component | Details |\n")
                    md_content.append("|-----------|----------|\n")
                    
                    for key, value in components.items():
                        if isinstance(value, dict):
                            # Format nested dictionary
                            details = []
                            for subkey, subvalue in value.items():
                                details.append(f"{subkey}: {subvalue}")
                            detail_str = ", ".join(details)
                            md_content.append(f"| {key} | {detail_str} |\n")
                        else:
                            md_content.append(f"| {key} | {value} |\n")
                
                md_content.append("\n")
            
            # Instructions section
            if 'instructions' in data:
                md_content.append("## Preparation Instructions\n\n")
                instructions = data['instructions']
                if isinstance(instructions, list):
                    for i, instruction in enumerate(instructions, 1):
                        md_content.append(f"{i}. {instruction}\n")
                else:
                    md_content.append(f"{instructions}\n")
                md_content.append("\n")
            
            # Additional properties
            excluded_keys = {'medium_id', 'name', 'description', 'source', 'reference', 'pH', 'components', 'instructions'}
            additional_props = {k: v for k, v in data.items() if k not in excluded_keys}
            
            if additional_props:
                md_content.append("## Additional Information\n\n")
                for key, value in additional_props.items():
                    formatted_key = key.replace('_', ' ').title()
                    if isinstance(value, (dict, list)):
                        md_content.append(f"**{formatted_key}:**\n```json\n{json.dumps(value, indent=2)}\n```\n\n")
                    else:
                        md_content.append(f"**{formatted_key}:** {value}\n\n")
        
        else:
            # Unknown data format
            md_content.append("# Unknown Composition Data Format\n\n")
            md_content.append("```json\n")
            md_content.append(json.dumps(data, indent=2))
            md_content.append("\n```\n\n")
        
        # Footer with metadata
        md_content.append("---\n")
        md_content.append("*Converted from MediaDive JSON composition data*\n")
        
        return "".join(md_content)
    
    async def convert_json_to_markdown(self, json_path: Path) -> bool:
        """Convert a single JSON composition file to markdown."""
        output_path = self.get_output_filename(json_path)
        
        # Skip if already converted
        if output_path.exists():
            logger.info(f"Skipping {json_path.name} (already converted)")
            self.skipped_count += 1
            return True
        
        try:
            logger.info(f"Converting {json_path.name} to markdown...")
            
            # Read and parse JSON
            async with aiofiles.open(json_path, 'r', encoding='utf-8') as f:
                json_content = await f.read()
            
            try:
                data = json.loads(json_content)
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in {json_path.name}: {e}")
                self.failed_count += 1
                return False
            
            # Convert to markdown
            markdown_content = self.format_composition_data(data)
            
            # Write markdown file
            async with aiofiles.open(output_path, 'w', encoding='utf-8') as f:
                await f.write(markdown_content)
            
            logger.info(f"Successfully converted {json_path.name} -> {output_path.name}")
            self.converted_count += 1
            return True
            
        except Exception as e:
            logger.error(f"Error converting {json_path.name}: {e}")
            self.failed_count += 1
            return False
    
    async def convert_all_json_files(self):
        """Convert all JSON composition files to markdown."""
        json_files = self.get_json_files()
        
        if not json_files:
            logger.warning("No JSON composition files found to convert")
            return
        
        logger.info(f"Starting conversion of {len(json_files)} JSON files...")
        
        # Create semaphore to limit concurrent conversions
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def convert_with_semaphore(json_path):
            async with semaphore:
                await self.convert_json_to_markdown(json_path)
        
        # Process JSON files concurrently
        tasks = [convert_with_semaphore(json_path) for json_path in json_files]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info(f"Conversion complete. Success: {self.converted_count}, Failed: {self.failed_count}, Skipped: {self.skipped_count}")
    
    def create_summary_report(self):
        """Create a summary report of the conversion process."""
        report_path = self.output_dir / "conversion_summary.md"
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write("# JSON to Markdown Conversion Summary\n\n")
                f.write(f"**Total JSON files processed:** {self.converted_count + self.failed_count + self.skipped_count}\n")
                f.write(f"**Successfully converted:** {self.converted_count}\n")
                f.write(f"**Failed conversions:** {self.failed_count}\n")
                f.write(f"**Skipped (already converted):** {self.skipped_count}\n\n")
                
                f.write("## Converted Files\n\n")
                markdown_files = list(self.output_dir.glob("*.md"))
                markdown_files = [f for f in markdown_files if f.name != "conversion_summary.md"]
                
                for md_file in sorted(markdown_files):
                    f.write(f"- [{md_file.name}](./{md_file.name})\n")
            
            logger.info(f"Summary report created: {report_path}")
            
        except Exception as e:
            logger.error(f"Error creating summary report: {e}")

async def main():
    """Main function to convert JSON composition files to markdown."""
    converter = JSONToMarkdownConverter(
        input_dir="media_pdfs",  # Look for JSON files in same directory as PDFs
        output_dir="media_compositions",
        max_concurrent=10
    )
    
    await converter.convert_all_json_files()
    converter.create_summary_report()

if __name__ == "__main__":
    asyncio.run(main())