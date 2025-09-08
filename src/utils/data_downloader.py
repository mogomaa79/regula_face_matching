from __future__ import annotations
import os
import json
import requests
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
from tqdm import tqdm
import time

def download_image(url: str, output_path: Path, timeout: int = 30, max_retries: int = 3) -> bool:
    """Download an image from URL to the specified path."""
    if not url or pd.isna(url) or str(url).strip() == '':
        print(f"⚠️  Empty URL, skipping download to {output_path}")
        return False
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, timeout=timeout, stream=True)
            response.raise_for_status()
            
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            print(f"✅ Downloaded: {output_path.name}")
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
            continue
    
    print(f"❌ Failed to download after {max_retries} attempts: {url}")
    return False

def process_csv_file(csv_path: Path, data_root: Path, category: str) -> Dict[str, int]:
    """Process a single CSV file and download images."""
    
    if not csv_path.exists():
        print(f"❌ CSV file not found: {csv_path}")
        return {"processed": 0, "success": 0, "failed": 0}
    
    df = pd.read_csv(csv_path)
    
    # Find maid ID column (handle various naming conventions)
    maid_id_col = None
    for col in df.columns:
        if col.lower().replace(' ', '_') in ['maid_id', 'maid_id', 'id'] or 'maid' in col.lower():
            maid_id_col = col
            break
    
    if not maid_id_col:
        print(f"❌ No maid ID column found in {csv_path}")
        print(f"Available columns: {list(df.columns)}")
        return {"processed": 0, "success": 0, "failed": 0}
    
    # Try to detect image URL columns
    image_url_columns = []
    for col in df.columns:
        # Check if column contains URLs (not just passport numbers or other text)
        if any(keyword in col.lower() for keyword in ['url', 'link', 'image', 'photo', 'face']) or \
           ('passport' in col.lower() and any(url_keyword in col.lower() for url_keyword in ['rejected', 'link', 'url', 'download'])):
            # Check if this column actually contains URLs by sampling first few non-null values
            sample_values = df[col].dropna().head(3)
            if any('http' in str(val) for val in sample_values):
                # Avoid duplicate columns (like .1 suffix)
                if not any(col.replace('.1', '').replace('.2', '') == existing.replace('.1', '').replace('.2', '') for existing in image_url_columns):
                    image_url_columns.append(col)
    
    if not image_url_columns:
        print(f"⚠️  No image URL columns detected in {csv_path}")
        print(f"Available columns: {list(df.columns)}")
        return {"processed": 0, "success": 0, "failed": 0}
    
    print(f"📊 Processing {len(df)} rows from {csv_path}")
    print(f"🆔 Using maid ID column: {maid_id_col}")
    print(f"🔗 Detected image URL columns: {image_url_columns}")
    
    stats = {"processed": 0, "success": 0, "failed": 0}
    
    for index, row in tqdm(df.iterrows(), total=len(df), desc=f"Processing {category}"):
        stats["processed"] += 1
        maid_id = str(row[maid_id_col])
        
        # Create maid directory
        maid_dir = data_root / category / maid_id
        maid_dir.mkdir(parents=True, exist_ok=True)
        
        # Download images
        download_success = True
        downloaded_files = {}
        
        for i, url_col in enumerate(image_url_columns):
            url = row.get(url_col, '')
            if pd.isna(url) or str(url).strip() == '':
                continue
                
            # Determine image type and create appropriate filename
            if any(keyword in url_col.lower() for keyword in ['passport', 'document', 'id']):
                filename = f"{maid_id}_passport.jpg"
                image_type = "passport"
            elif any(keyword in url_col.lower() for keyword in ['photo', 'face', 'selfie', 'live']):
                filename = f"{maid_id}_face.jpg" 
                image_type = "face_photo"
            else:
                # Default fallback based on column index
                filename = f"{maid_id}_image_{i}.jpg"
                image_type = f"image_{i}"
            
            output_path = maid_dir / filename
            
            success = download_image(url, output_path)
            if success:
                downloaded_files[image_type] = {
                    "filename": filename,
                    "url": str(url),
                    "column": url_col,
                    "path": str(output_path.relative_to(data_root.parent))
                }
            else:
                download_success = False
        
        # Create info.json with all row data
        info_data = {
            "maid_id": maid_id,
            "category": category,
            "csv_source": str(csv_path.name),
            "downloaded_images": downloaded_files,
            "original_data": row.to_dict(),
            "processing_timestamp": pd.Timestamp.now().isoformat()
        }
        
        info_path = maid_dir / "info.json"
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump(info_data, f, indent=2, ensure_ascii=False, default=str)
        
        if download_success and downloaded_files:
            stats["success"] += 1
        else:
            stats["failed"] += 1
        
        # Small delay to be respectful to servers
        time.sleep(0.1)
    
    return stats

def main(csv_files: Dict[str, str], data_root: str = "data") -> None:
    """
    Main function to process CSV files and download images.
    
    Args:
        csv_files: Dictionary mapping category names to CSV file paths
                  e.g., {"CC": "rejected_CC.csv", "MV": "rejected_MV.csv"}
        data_root: Root directory for data storage
    """
    
    data_path = Path(data_root)
    data_path.mkdir(parents=True, exist_ok=True)
    
    total_stats = {"processed": 0, "success": 0, "failed": 0}
    
    print(f"🚀 Starting image download process...")
    print(f"📁 Data root: {data_path.absolute()}")
    print()
    
    for category, csv_file in csv_files.items():
        print(f"📋 Processing category: {category}")
        csv_path = Path(csv_file)
        
        stats = process_csv_file(csv_path, data_path, category)
        
        # Update total stats
        for key in total_stats:
            total_stats[key] += stats[key]
        
        print(f"✅ {category} complete: {stats['success']}/{stats['processed']} successful")
        print()
    
    print(f"🎉 Download process complete!")
    print(f"📊 Total processed: {total_stats['processed']}")
    print(f"✅ Total successful: {total_stats['success']}")
    print(f"❌ Total failed: {total_stats['failed']}")
    
    if total_stats['success'] > 0:
        success_rate = (total_stats['success'] / total_stats['processed']) * 100
        print(f"📈 Success rate: {success_rate:.1f}%")

if __name__ == "__main__":
    # Example usage - modify these paths according to your CSV files
    csv_files = {
        "CC": "rejected_CC.csv",
        "MV": "rejected_MV.csv"
    }
    
    main(csv_files)
