from __future__ import annotations
import os, base64
from pathlib import Path
from typing import List, Dict
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

from src.utils.files import list_image_files, choose_passport_and_selfie
from src.adapters.face_client import match_passport_and_selfie
from src.utils.sheets_uploader import upload_to_sheets

load_dotenv()

DATA_ROOT = Path(os.getenv("DATA_ROOT", "data/MV"))
RESULTS_CSV = Path(os.getenv("RESULTS_CSV", "results/MV_results.csv"))
THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.90"))
SAVE_CROPS = os.getenv("SAVE_CROPS", "false").lower() == "true"
CROPS_DIR = Path(os.getenv("CROPS_DIR", "results/crops"))

def _save_b64_image(b64: str, out_path: Path):
    if not b64:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))

def _extract_id_from_filename(filepath: Path) -> str:
    """Extract ID from filename by splitting on underscore and taking first part."""
    filename = filepath.stem
    parts = filename.split('_')
    return parts[0] if parts else filename

def _should_files_match(passport_path: Path, face_photo_path: Path) -> bool:
    """Check if files should match based on their filename IDs."""
    passport_id = _extract_id_from_filename(passport_path)
    face_photo_id = _extract_id_from_filename(face_photo_path)
    
    # Return True if both IDs are non-empty and match
    return bool(passport_id and face_photo_id and passport_id == face_photo_id)

def _assess_match_result(should_match: bool, actual_match: bool) -> str:
    """Assess the difference between expected and actual match results."""
    if should_match and actual_match:
        return "true_positive"
    elif not should_match and not actual_match:
        return "true_negative"
    elif should_match and not actual_match:
        return "false_negative"
    else:  # not should_match and actual_match
        return "false_positive"


def run() -> None:
    maid_dirs = [p for p in DATA_ROOT.iterdir() if p.is_dir()]

    rows: List[Dict] = []
    for maid_dir in tqdm(maid_dirs, desc="maids"):
        maid_id = maid_dir.name
        images = list_image_files(maid_dir)
        if len(images) < 2:
            rows.append({"maid_id": maid_id, "status": "skipped:not_enough_images"})
            continue

        passport, selfie = choose_passport_and_selfie(images)
        if not passport or not selfie:
            rows.append({"maid_id": maid_id, "status": "skipped:cant_choose_pair"})
            continue

        try:
            res = match_passport_and_selfie(
                passport.read_bytes(),
                selfie.read_bytes(),
                threshold=THRESHOLD,
                save_crops=SAVE_CROPS
            )

            # Save crops for QA/debug
            if SAVE_CROPS:
                _save_b64_image(res.passport_crop_b64, CROPS_DIR / maid_id / "passport_crop.jpg")
                _save_b64_image(res.selfie_crop_b64,   CROPS_DIR / maid_id / "selfie_crop.jpg")

            # Check if files should match based on filename IDs
            should_match = _should_files_match(passport, selfie)
            actual_match = bool(res.decision)
            match_assessment = _assess_match_result(should_match, actual_match)

            rows.append({
                "maid_id": maid_id,
                "passport_path": str(passport),
                "face_photo_path": str(selfie),
                "passport_id": _extract_id_from_filename(passport),
                "face_photo_id": _extract_id_from_filename(selfie),
                "should_match": should_match,
                "similarity": res.similarity,
                "match": actual_match,
                "match_assessment": match_assessment,
                "reason": res.reason,
                "status": "ok",
            })

        except Exception as e:
            rows.append({
                "maid_id": maid_id,
                "passport_path": str(passport) if passport else "",
                "face_photo_path": str(selfie) if selfie else "",
                "passport_id": _extract_id_from_filename(passport) if passport else "",
                "face_photo_id": _extract_id_from_filename(selfie) if selfie else "",
                "should_match": False,
                "similarity": 0.0,
                "match": False,
                "match_assessment": "error",
                "reason": f"error:{e}",
                "status": f"error:{e}",
            })

    # write CSV
    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    df.to_csv(RESULTS_CSV, index=False)
    print(f"💾 Saved results: {RESULTS_CSV}")
    
    # Show summary
    total_maids = len(df)
    successful_matches = len(df[df['status'] == 'ok'])
    if successful_matches > 0:
        matches = len(df[(df['status'] == 'ok') & (df['match'] == True)])
        avg_similarity = df[df['status'] == 'ok']['similarity'].mean()
        
        # Additional statistics for filename-based matching
        should_match_count = len(df[(df['status'] == 'ok') & (df['should_match'] == True)])
        correct_predictions = len(df[(df['status'] == 'ok') & (df['match_assessment'].isin(['correct_positive', 'correct_negative']))])
        accuracy = correct_predictions / successful_matches if successful_matches > 0 else 0
        
        print(f"📊 Processed {total_maids} maids: {successful_matches} successful, {matches} matches (avg similarity: {avg_similarity:.3f})")
        print(f"📋 Filename analysis: {should_match_count} should match, {correct_predictions} correct predictions (accuracy: {accuracy:.1%})")
    else:
        print(f"📊 Processed {total_maids} maids: {successful_matches} successful")
    
    # Upload to Google Sheets
    upload_success = upload_to_sheets(RESULTS_CSV)
    if upload_success:
        print(f"🎉 Face matching complete! Results saved and uploaded.")
    else:
        print(f"⚠️  Face matching complete! Results saved locally (upload failed).")

if __name__ == "__main__":
    run()
