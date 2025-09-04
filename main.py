from __future__ import annotations
import os, base64
from pathlib import Path
from dataclasses import asdict
from typing import List, Dict
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv

from src.utils.files import list_image_files, choose_passport_and_selfie
from src.adapters.face_client import match_passport_and_selfie
from src.utils.sheets_uploader import upload_to_sheets

load_dotenv()

DATA_ROOT = Path(os.getenv("DATA_ROOT", "data/faces"))
RESULTS_CSV = Path(os.getenv("RESULTS_CSV", "results/face_results.csv"))
THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.85"))
SAVE_CROPS = os.getenv("SAVE_CROPS", "false").lower() == "true"
CROPS_DIR = Path(os.getenv("CROPS_DIR", "results/crops"))

def _save_b64_image(b64: str, out_path: Path):
    if not b64:
        return
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(base64.b64decode(b64))


def run() -> None:
    maid_dirs = [p for p in DATA_ROOT.iterdir() if p.is_dir()]

    rows: List[Dict] = []
    for maid_dir in tqdm(maid_dirs, desc="maids"):
        maid_id = maid_dir.name
        images = list_image_files(maid_dir)
        if len(images) < 2:
            rows.append({"inputs.maid_id": maid_id, "status": "skipped:not_enough_images"})
            continue

        passport, selfie = choose_passport_and_selfie(images)
        if not passport or not selfie:
            rows.append({"inputs.maid_id": maid_id, "status": "skipped:cant_choose_pair"})
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

            rows.append({
                "inputs.maid_id": maid_id,
                "inputs.passport_path": str(passport),
                "inputs.selfie_path": str(selfie),
                "outputs.similarity": res.similarity,
                "outputs.match": res.decision,
                "outputs.reason": res.reason,
                "status": "ok",
            })

        except Exception as e:
            rows.append({
                "inputs.maid_id": maid_id,
                "inputs.passport_path": str(passport) if passport else "",
                "inputs.selfie_path": str(selfie) if selfie else "",
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
        matches = len(df[(df['status'] == 'ok') & (df['outputs.match'] == True)])
        avg_similarity = df[df['status'] == 'ok']['outputs.similarity'].mean()
        print(f"📊 Processed {total_maids} maids: {successful_matches} successful, {matches} matches (avg similarity: {avg_similarity:.3f})")
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
