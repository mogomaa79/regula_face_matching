from __future__ import annotations
import os, base64
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass
from contextlib import contextmanager
import time
import random

FACE_API_URL = os.getenv("FACE_API_URL", "http://localhost:41101")
API_TIMEOUT = int(os.getenv("API_TIMEOUT", "30"))
API_MAX_RETRIES = int(os.getenv("API_MAX_RETRIES", "3"))
API_RETRY_DELAY = float(os.getenv("API_RETRY_DELAY", "1.0"))
API_TIMEOUT_RETRY_WAIT = int(os.getenv("API_TIMEOUT_RETRY_WAIT", "30"))

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

@contextmanager
def sdk():
    # Regula example shows host without /api; client adds it internally.
    # https://github.com/regulaforensics/FaceSDK-web-python-client
    with FaceSdk(host=FACE_API_URL) as client:
        yield client

def match_passport_and_selfie(passport_bytes: bytes, selfie_bytes: bytes, threshold: float = 0.85) -> FaceMatchResult:
    """
    Match passport and selfie images using Regula Face SDK.
    
    Uses direct REST API with detectAll=True to match website behavior exactly.
    Detects ALL faces in both images and returns the HIGHEST similarity score.
    
    Args:
        passport_bytes: Raw bytes of passport image (may contain multiple faces/ghost portraits)
        selfie_bytes: Raw bytes of selfie image (may contain multiple faces)
        threshold: Similarity threshold for match decision
        
    Returns:
        FaceMatchResult with the highest similarity score found among all face comparisons
    """
    
    # Use direct REST API with detectAll=True (EXACT website format)
    try:
        import requests
        import base64
        import json
        
        # Use direct REST API with detectAll=True (website format)
        
        # Create EXACT website format with detectAll=True
        request_data = {
            "images": [
                {
                    "data": base64.b64encode(passport_bytes).decode('utf-8'),
                    "index": 0,
                    "detectAll": True,
                    "type": 3
                },
                {
                    "data": base64.b64encode(selfie_bytes).decode('utf-8'),
                    "index": 1,
                    "detectAll": True,
                    "type": 3
                }
            ]
        }
        
        # Send direct REST request with retries and exponential backoff
        max_retries = API_MAX_RETRIES
        base_timeout = API_TIMEOUT
        
        for attempt in range(max_retries):
            try:
                timeout = base_timeout + (attempt * 10)  # Increase timeout with each retry
                response = requests.post(
                    f"{FACE_API_URL}/api/match",
                    json=request_data,
                    headers={"Content-Type": "application/json"},
                    timeout=timeout
                )
                
                # Check for retryable status codes
                retryable_codes = [429, 502, 503, 504]  # Rate limit, Bad Gateway, Service Unavailable, Gateway Timeout
                if response.status_code in retryable_codes:
                    if attempt < max_retries - 1:
                        # Exponential backoff with jitter
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        error_name = {
                            429: "Rate limited",
                            502: "Bad Gateway", 
                            503: "Service Unavailable",
                            504: "Gateway Timeout"
                        }.get(response.status_code, f"HTTP {response.status_code}")
                        print(f"⏱️  {error_name}, waiting {wait_time:.1f}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"❌ {response.status_code} error exceeded after {max_retries} attempts")
                        return FaceMatchResult(
                            similarity=0.0,
                            decision=False,
                            reason=f"http_{response.status_code}_exceeded",
                            meta={"api_method": "direct_rest", "error": f"HTTP {response.status_code}", "attempts": max_retries}
                        )
                
                # For non-retryable status codes, break out of retry loop
                if response.status_code != 200:
                    break
                    
                # Process successful response
                try:
                    result = response.json()
                except json.JSONDecodeError:
                    if attempt < max_retries - 1:
                        wait_time = API_TIMEOUT_RETRY_WAIT  # Fixed wait time for invalid responses
                        print(f"⏱️  Invalid JSON response, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return FaceMatchResult(
                            similarity=0.0,
                            decision=False,
                            reason="invalid_json_response",
                            meta={"api_method": "direct_rest", "error": "Invalid JSON response", "attempts": max_retries}
                        )
                
                # Check if results exist and are valid
                if 'results' in result and result['results']:
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
                        # No valid similarities found - return immediately (no retry)
                        return FaceMatchResult(
                            similarity=0.0,
                            decision=False,
                            reason="no_valid_similarities_found",
                            meta={"api_method": "direct_rest", "raw_response": result, "attempts": attempt + 1}
                        )
                    
                    # Success! Process the results
                    sim = best_similarity
                    decision = sim >= threshold
                    
                    # Create detailed reason with face comparison info
                    total_comparisons = len(all_similarities)
                    if total_comparisons > 1:
                        reason = f"ok (best of {total_comparisons} face comparisons)" if decision else f"below threshold {threshold} (best of {total_comparisons} face comparisons)"
                    else:
                        reason = "ok" if decision else f"below threshold {threshold}"

                    # Enhanced metadata with detailed face comparison info
                    meta = {
                        "api_method": "direct_rest_detectall",
                        "total_face_comparisons": total_comparisons,
                        "all_similarities": all_similarities,
                        "best_similarity": best_similarity,
                        "average_similarity": sum(all_similarities) / len(all_similarities) if all_similarities else 0.0,
                        "multiple_faces_detected": total_comparisons > 1,
                        "ghost_portrait_handling": True,
                        "detection_mode": "detectAll_true_both_images",
                        "website_compatible": True,
                        "retries_used": attempt
                    }
                    
                    return FaceMatchResult(similarity=sim, decision=decision, reason=reason, meta=meta)
                    
                else:
                    # No results in response - could be API overload, retry
                    if attempt < max_retries - 1:
                        wait_time = API_TIMEOUT_RETRY_WAIT  # Fixed wait time for API overload
                        print(f"⏱️  API returned no results, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return FaceMatchResult(
                            similarity=0.0,
                            decision=False,
                            reason="rest_api_no_results",
                            meta={"api_method": "direct_rest", "raw_response": result, "attempts": max_retries}
                        )
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    wait_time = API_TIMEOUT_RETRY_WAIT  # Fixed wait time for timeouts
                    print(f"⏱️  Request timeout, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Request timeout after {max_retries} attempts")
                    return FaceMatchResult(
                        similarity=0.0,
                        decision=False,
                        reason="request_timeout",
                        meta={"api_method": "direct_rest", "error": "Request timeout", "attempts": max_retries}
                    )
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)
                    print(f"⏱️  Request error ({e}), waiting {wait_time:.1f}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"❌ Request failed after {max_retries} attempts: {e}")
                    return FaceMatchResult(
                        similarity=0.0,
                        decision=False,
                        reason="request_failed",
                        meta={"api_method": "direct_rest", "error": str(e), "attempts": max_retries}
                    )
        
        # If we exit the retry loop, handle non-200 responses
        if response.status_code != 200:
            return FaceMatchResult(
                similarity=0.0,
                decision=False,
                reason=f"rest_api_error_{response.status_code}",
                meta={"api_method": "direct_rest", "error": response.text, "attempts": max_retries}
            )
            
    except Exception as e:
        print(f"❌ REST API approach failed: {e}")
        return FaceMatchResult(
            similarity=0.0,
            decision=False,
            reason=f"rest_api_exception: {str(e)}",
            meta={"api_method": "direct_rest", "error": str(e)}
        )
