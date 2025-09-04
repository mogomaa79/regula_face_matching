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
        # det.results[0].face.crop.image (base64) — structure per docs
        # https://docs.regulaforensics.com/face-sdk-web-service/#tag/Detect
        r0 = (getattr(det, "results", []) or [None])[0]
        face = getattr(r0, "face", None)
        crop = getattr(face, "crop", None)
        b64 = getattr(crop, "image", None)
        return b64
    except Exception:
        return None

def match_passport_and_selfie(passport_bytes: bytes, selfie_bytes: bytes, threshold: float = 0.85, save_crops: bool = False) -> FaceMatchResult:
    with sdk() as client:
        req = MatchRequest(
            images=[
                # DOCUMENT_PRINTED for a scanned/photographed passport page;
                # LIVE for a phone/selfie. (Regula's example shows DOCUMENT_RFID too.)
                MatchImage(index=1, data=passport_bytes, type=ImageSource.DOCUMENT_PRINTED),
                MatchImage(index=2, data=selfie_bytes,   type=ImageSource.LIVE),
            ],
            thumbnails=True,
        )
        resp = client.match_api.match(req)
        # resp.results[0].similarity is the main score (0..1)
        # https://docs.regulaforensics.com/face-sdk-web-service/#tag/Match
        res0 = (getattr(resp, "results", []) or [None])[0]
        sim = float(getattr(res0, "similarity", 0.0) or 0.0)
        decision = sim >= threshold
        reason = "ok" if decision else f"below threshold {threshold}"

        pcrop = scrop = None
        if save_crops:
            pcrop = _detect_first_crop_b64(client, passport_bytes)
            scrop = _detect_first_crop_b64(client, selfie_bytes)

        # provide a JSONable meta dump
        meta = client.api_client.sanitize_for_serialization(resp) if hasattr(client, "api_client") else {}
        return FaceMatchResult(similarity=sim, decision=decision, reason=reason, meta=meta, passport_crop_b64=pcrop, selfie_crop_b64=scrop)
