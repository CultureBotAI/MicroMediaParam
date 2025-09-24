#!/usr/bin/env python3
"""
Update Chemical Properties Database

Convenient script to update chemical_properties.tsv with new compound data
from IUPAC and other authoritative sources.

Usage:
    python update_chemical_properties.py --help
    python update_chemical_properties.py --update-from-mappings
    python update_chemical_properties.py --add-compounds "sodium chloride,glucose"
    python update_chemical_properties.py --full-update

Author: MicroMediaParam Project
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.chem.iupac.pipeline import ChemicalDataPipeline
from src.chem.iupac.config import get_config, PRIORITY_COMPOUNDS

async def main():
    """Main function for updating chemical properties."""
    parser = argparse.ArgumentParser(
        description="Update chemical_properties.tsv with new compound data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update with compounds from existing mapping files
  python update_chemical_properties.py --update-from-mappings
  
  # Add specific compounds
  python update_chemical_properties.py --add-compounds "sodium chloride,glucose,calcium carbonate"
  
  # Full update with priority compounds
  python update_chemical_properties.py --full-update
  
  # Test with a few compounds (no download)
  python update_chemical_properties.py --test-mode
        """
    )
    
    parser.add_argument(
        "--update-from-mappings",
        action="store_true",
        help="Update TSV with compounds from existing mapping files"
    )
    
    parser.add_argument(
        "--add-compounds",
        type=str,
        help="Comma-separated list of compounds to add"
    )
    
    parser.add_argument(
        "--full-update",
        action="store_true", 
        help="Full update including priority compounds and mappings"
    )
    
    parser.add_argument(
        "--test-mode",
        action="store_true",
        help="Test mode - process a few compounds without downloading"
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="chemical_properties.tsv",
        help="Output TSV file (default: chemical_properties.tsv)"
    )
    
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/chemical_processing",
        help="Directory for processing data"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually doing it"
    )
    
    args = parser.parse_args()
    
    # Create pipeline
    pipeline = ChemicalDataPipeline(
        data_dir=Path(args.data_dir),
        chemical_properties_file=Path(args.output_file)
    )
    
    print("🧪 MicroMediaParam Chemical Properties Updater")
    print("=" * 50)
    
    try:
        if args.test_mode:
            print("🧪 Running in test mode...")
            test_compounds = ["sodium chloride", "glucose", "calcium carbonate"]
            
            if args.dry_run:
                print(f"Would download and process: {test_compounds}")
            else:
                await pipeline.download_chemical_data(test_compounds)
                pipeline.process_chemical_data()
                pipeline.generate_chemical_properties_tsv(merge_with_existing=True)
                print(f"✅ Test completed - check {args.output_file}")
        
        elif args.update_from_mappings:
            print("📊 Updating from existing compound mappings...")
            
            if args.dry_run:
                # Analyze what would be updated
                config = get_config()
                mappings_files = [Path(f) for f in config['default_mapping_files']]
                target_compounds = pipeline.analyze_existing_compounds(mappings_files)
                print(f"Would download data for {len(target_compounds)} compounds")
                print(f"First 10 compounds: {target_compounds[:10]}")
            else:
                await pipeline.update_chemical_properties()
                print(f"✅ Update completed - check {args.output_file}")
        
        elif args.add_compounds:
            compounds = [c.strip() for c in args.add_compounds.split(',')]
            print(f"➕ Adding {len(compounds)} compounds...")
            
            if args.dry_run:
                print(f"Would add compounds: {compounds}")
            else:
                await pipeline.update_chemical_properties(additional_compounds=compounds)
                print(f"✅ Compounds added - check {args.output_file}")
        
        elif args.full_update:
            print("🔄 Running full update...")
            print(f"📋 Will include {len(PRIORITY_COMPOUNDS)} priority compounds")
            
            if args.dry_run:
                print("Would run full pipeline including:")
                print("- Analyze existing mapping files")
                print("- Download priority compounds")
                print("- Process all chemical data")
                print("- Generate updated TSV file")
            else:
                await pipeline.run_full_pipeline()
                print(f"✅ Full update completed - check {args.output_file}")
        
        else:
            parser.print_help()
            print("\n💡 Quick start: python update_chemical_properties.py --update-from-mappings")
    
    except KeyboardInterrupt:
        print("\n⏹️  Update interrupted by user")
    except Exception as e:
        print(f"\n❌ Update failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())