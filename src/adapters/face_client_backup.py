from __future__ import annotations
import os, base64
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from contextlib import contextmanager

FACE_API_URL = os.getenv("FACE_API_URL", "http://localhost:41101")

# Import Regula Face SDK components
from regula.facesdk.webclient.ext import FaceSdk, DetectRequest
from regula.facesdk.webclient import MatchImage, MatchRequest
from regula.facesdk.webclient.gen.model.image_source import ImageSource

@dataclass
class FaceMatchResult:
    similarity: float
    decision: bool
    reason: str
    meta: Dict[str, Any]
    passport_crop_b64: Optional[str] = None
    selfie_crop_b64: Optional[str] = None

@contextmanager
def sdk():
    # Regula example shows host without /api; client adds it internally.
    # https://github.com/regulaforensics/FaceSDK-web-python-client
    with FaceSdk(host=FACE_API_URL) as client:
        yield client

def _detect_first_crop_b64(client: FaceSdk, image_bytes: bytes) -> Optional[str]:
    try:
        det = client.match_api.detect(DetectRequest(image=image_bytes))
        r0 = (getattr(det, "results", []) or [None])[0]
        face = getattr(r0, "face", None)
        crop = getattr(face, "crop", None)
        b64 = getattr(crop, "image", None)
        return b64
    except Exception:
        return None


def match_passport_and_selfie(passport_bytes: bytes, selfie_bytes: bytes, threshold: float = 0.85, save_crops: bool = False) -> FaceMatchResult:
    """
    Match passport and selfie images using Regula Face SDK.
    
    Detects ALL faces in both images and returns the HIGHEST similarity score.
    This handles ghost portraits and multiple faces in passport images.
    
    Args:
        passport_bytes: Raw bytes of passport image (may contain multiple faces/ghost portraits)
        selfie_bytes: Raw bytes of selfie image (may contain multiple faces)
        threshold: Similarity threshold for match decision
        save_crops: Whether to extract and save face crops
        
    Returns:
        FaceMatchResult with the highest similarity score found among all face comparisons
    """
    
    # Use direct REST API with detectAll=True (same as website)
    try:
        import requests
        import base64
        import json
        
        print("🔍 Using direct REST API with detectAll=True...")
        
        # Create EXACT website format with detectAll=True
        request_data = {
            "images": [
                {
                    "data": base64.b64encode(passport_bytes).decode('utf-8'),
                    "index": 0,
                    "detectAll": True,
                    "type": 1
                },
                {
                    "data": base64.b64encode(selfie_bytes).decode('utf-8'),
                    "index": 1,
                    "detectAll": True,
                    "type": 1
                }
            ]
        }
        
        # Send direct REST request
        response = requests.post(
            f"{FACE_API_URL}/api/match",
            json=request_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            # Parse the response for actual results
            if 'results' in result and result['results']:
                print(f"🎉 SUCCESS! Got {len(result['results'])} results from REST API")
                
                # Extract all similarity scores and find the BEST one
                all_similarities = []
                best_similarity = 0.0
                
                for match_result in result['results']:
                    if 'similarity' in match_result:
                        sim = float(match_result['similarity'])
                        all_similarities.append(sim)
                        if sim > best_similarity:
                            best_similarity = sim
                
                if not all_similarities:
                    return FaceMatchResult(
                        similarity=0.0,
                        decision=False,
                        reason="no_valid_similarities_found",
                        meta={"api_method": "direct_rest", "raw_response": result}
                    )
                
                # Use direct REST results
                results = all_similarities  # For compatibility with existing code below
                
            else:
                print("❌ REST API returned no results")
                return FaceMatchResult(
                    similarity=0.0,
                    decision=False,
                    reason="rest_api_no_results",
                    meta={"api_method": "direct_rest", "raw_response": result}
                )
        else:
            print(f"❌ REST API failed: {response.status_code} - {response.text}")
            return FaceMatchResult(
                similarity=0.0,
                decision=False,
                reason=f"rest_api_error_{response.status_code}",
                meta={"api_method": "direct_rest", "error": response.text}
            )
            
    except Exception as e:
        print(f"❌ REST API approach failed: {e}")
        return FaceMatchResult(
            similarity=0.0,
            decision=False,
            reason=f"rest_api_exception: {str(e)}",
            meta={"api_method": "direct_rest", "error": str(e)}
        )
    
    # Process the results (same logic as before)
    if not results:
        return FaceMatchResult(
            similarity=0.0,
            decision=False,
            reason="no_face_comparisons_found",
            meta={"error": "No face matching results returned"}
        )
        
        # Handle ALL faces - find the HIGHEST similarity among all comparisons
        results = getattr(resp, "results", []) or []
        
        if not results:
            return FaceMatchResult(
                similarity=0.0,
                decision=False,
                reason="no_face_comparisons_found",
                meta={"error": "No face matching results returned"}
            )
        
        # Extract all similarity scores and find the BEST one
        all_similarities = []
        best_similarity = 0.0
        
        for result in results:
            if result and hasattr(result, 'similarity'):
                sim = float(getattr(result, "similarity", 0.0) or 0.0)
                all_similarities.append(sim)
                if sim > best_similarity:
                    best_similarity = sim
            else:
                all_similarities.append(0.0)
        
        # Use the HIGHEST similarity found among all face comparisons
        sim = best_similarity
        decision = sim >= threshold
        
        # Create detailed reason with face comparison info
        total_comparisons = len(all_similarities)
        if total_comparisons > 1:
            reason = f"ok (best of {total_comparisons} face comparisons)" if decision else f"below threshold {threshold} (best of {total_comparisons} face comparisons)"
        else:
            reason = "ok" if decision else f"below threshold {threshold}"

        pcrop = scrop = None
        if save_crops:
            pcrop = _detect_first_crop_b64(client, passport_bytes)
            scrop = _detect_first_crop_b64(client, selfie_bytes)

        # Enhanced metadata with detailed face comparison info
        meta = {}
        try:
            meta = client.api_client.sanitize_for_serialization(resp) if hasattr(client, "api_client") else {}
            # Add detailed comparison metadata
            meta.update({
                "total_face_comparisons": total_comparisons,
                "all_similarities": all_similarities,
                "best_similarity": best_similarity,
                "average_similarity": sum(all_similarities) / len(all_similarities) if all_similarities else 0.0,
                "multiple_faces_detected": total_comparisons > 1,
                "ghost_portrait_handling": True,
                "detection_mode": "all_faces_in_both_images"
            })
        except Exception as e:
            meta = {
                "metadata_error": str(e),
                "total_face_comparisons": total_comparisons,
                "all_similarities": all_similarities,
                "best_similarity": best_similarity
            }
        
        return FaceMatchResult(similarity=sim, decision=decision, reason=reason, meta=meta, passport_crop_b64=pcrop, selfie_crop_b64=scrop)