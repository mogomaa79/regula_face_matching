#!/usr/bin/env python3
"""
Data Download Script for Face Matching

This script downloads images from CSV files containing maid data and organizes
them into the proper folder structure for face matching analysis.

Usage:
    python download_data.py

Configuration:
    - Edit CSV_FILES dictionary below to specify your CSV file paths
    - Adjust DATA_ROOT if you want to change the output directory
    - Modify column detection logic in data_downloader.py if needed
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add src to path for imports
sys.path.append(str(Path(__file__).parent / "src"))

from utils.data_downloader import main as download_main

# Load environment variables
load_dotenv()

# Configuration
DATA_ROOT = os.getenv("DATA_ROOT", "data")

# CSV Files to process - UPDATE THESE PATHS
CSV_FILES = {
    "CC": "rejected_CC.csv",    # Path to CC (Credit Card?) CSV file
    "MV": "rejected_MV.csv",    # Path to MV (Money Transfer?) CSV file
}

def validate_csv_files():
    """Validate that CSV files exist before processing."""
    missing_files = []
    
    for category, csv_path in CSV_FILES.items():
        if not Path(csv_path).exists():
            missing_files.append(f"{category}: {csv_path}")
    
    if missing_files:
        print("❌ Missing CSV files:")
        for file in missing_files:
            print(f"   {file}")
        print()
        print("Please update the CSV_FILES dictionary in this script with correct paths.")
        return False
    
    return True

def main():
    """Main execution function."""
    print("🚀 Face Matching Data Download Script")
    print("=" * 50)
    print()
    
    # Validate CSV files exist
    if not validate_csv_files():
        sys.exit(1)
    
    print("📋 CSV Files to process:")
    for category, csv_path in CSV_FILES.items():
        file_size = Path(csv_path).stat().st_size / 1024  # KB
        print(f"   {category}: {csv_path} ({file_size:.1f} KB)")
    print()
    
    print(f"📁 Output directory: {Path(DATA_ROOT).absolute()}")
    print()
    
    # Confirm before proceeding
    response = input("Continue with download? (y/N): ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ Download cancelled.")
        sys.exit(0)
    
    print()
    
    # Start download process
    try:
        download_main(CSV_FILES, DATA_ROOT)
        
        print()
        print("🎯 Next steps:")
        print("1. Review downloaded images in the data/ folder")
        print("2. Run face matching: python main.py")
        print("3. Check results in results/face_results.csv")
        
    except KeyboardInterrupt:
        print("\n❌ Download interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
