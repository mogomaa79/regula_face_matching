from __future__ import annotations
import os
from pathlib import Path
from typing import List, Dict
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

from src.utils.files import list_image_files, choose_passport_and_selfie
from src.adapters.face_client import match_passport_and_selfie
from src.utils.sheets_uploader import upload_to_sheets

load_dotenv()

DATA_ROOT = Path(os.getenv("DATA_ROOT", "data/CC"))
RESULTS_CSV = Path(os.getenv("RESULTS_CSV", "results/CC_results.csv"))
THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.80"))

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
                threshold=THRESHOLD
            )

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
    
    # Upload to Google Sheets
    upload_to_sheets(RESULTS_CSV)

if __name__ == "__main__":
    run()
