"""
Aethra Gold Assessment API — Fully Offline Backend
- No Anthropic
- No external APIs
- Offline optical analysis
- Offline acoustic analysis
- Offline hallmark OCR
- FastAPI + OpenCV + NumPy + SciPy
- Dynamic normalization + blue/red-green spectral logic
- Confidence, fraud, consensus, valuation, XAI
"""

from __future__ import annotations

import asyncio
import base64
import io
import math
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import cv2
import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from scipy.io import wavfile
from scipy.signal import find_peaks
from scipy.fft import fft, fftfreq

# Optional offline OCR dependency:
# pip install pytesseract
# and install Tesseract locally on the machine.
try:
    import pytesseract
except Exception:
    pytesseract = None


# ═══════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════

ENABLE_CACHING = True
MAX_IMAGE_SIZE = 1200
JPEG_QUALITY = 85
RATE_LIMIT_PER_MINUTE = 20
RATE_LIMIT_WINDOW_SECONDS = 60

# Dynamic normalization sensitivity used in:
# alpha = 1.0 - (Iw / 255 * Sens)
SENSITIVITY = 0.55

# If pytesseract is installed in a non-default location, set it here:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ═══════════════════════════════════════════════════════════════════
# APP SETUP
# ═══════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Aethra Gold Assessment API",
    version="3.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1000)


# ═══════════════════════════════════════════════════════════════════
# SIMPLE IN-MEMORY RATE LIMITING
# ═══════════════════════════════════════════════════════════════════

rate_limit_store = defaultdict(list)

def check_rate_limit(identifier: str, limit: int = RATE_LIMIT_PER_MINUTE, window: int = RATE_LIMIT_WINDOW_SECONDS) -> bool:
    now = datetime.now()
    cutoff = now - timedelta(seconds=window)

    rate_limit_store[identifier] = [t for t in rate_limit_store[identifier] if t > cutoff]

    if len(rate_limit_store[identifier]) >= limit:
        return False

    rate_limit_store[identifier].append(now)
    return True


# ═══════════════════════════════════════════════════════════════════
# SCHEMAS
# ═══════════════════════════════════════════════════════════════════

class OpticalResult(BaseModel):
    lb_mean: float
    rg_mean: float
    confidence_score: float
    karat_estimate: str
    karat_range: str
    optical_score: float
    confidence_level: str  # green/yellow/red
    plating_risk: str      # low/medium/high
    alpha_scaling: float
    edge_diffusion_px: float
    luster_profile: str


class HallmarkResult(BaseModel):
    hallmark_detected: bool
    hallmark_text: Optional[str] = None
    hallmark_confidence: float = 0.0
    hallmark_validity: str = "missing"  # valid/suspicious/missing/unclear
    purity_from_hallmark: Optional[str] = None
    extracted_tokens: List[str] = Field(default_factory=list)
    ocr_raw_text: Optional[str] = None


class AcousticResult(BaseModel):
    f0_hz: float
    t60_seconds: float
    q_factor: float
    harmonic_ratio: float
    snr_db: float
    audio_score: float
    material_match: str
    decay_category: str
    confidence_level: str
    flagged_noise: bool


class ConsensusResult(BaseModel):
    final_score: float
    delta_integrity: float
    risk_level: str  # low/medium/high
    recommendation: str  # pre_approve/needs_verification/reject
    ltv_percent: Optional[float] = None
    max_loan_inr: Optional[float] = None
    weight_range_g: str
    purity_band: str
    estimated_value_inr: Optional[float] = None


class XAIResult(BaseModel):
    narrative: str
    optical_confidence: str
    acoustic_confidence: str
    hallmark_confidence: str
    overall_confidence: str
    fraud_flags: list[str] = Field(default_factory=list)
    trust_factors: list[str] = Field(default_factory=list)
    penalty_notes: list[str] = Field(default_factory=list)


class AssessmentResponse(BaseModel):
    session_id: str
    timestamp: float
    optical: OpticalResult
    hallmark: HallmarkResult
    acoustic: Optional[AcousticResult]
    consensus: ConsensusResult
    xai: XAIResult
    processing_time_ms: float


# ═══════════════════════════════════════════════════════════════════
# OFFLINE CONSTANTS
# ═══════════════════════════════════════════════════════════════════

KARAT_TABLE = [
    (0, 15, "24K", "24K", 100, "low"),
    (15, 35, "22K", "22K-24K", 92, "low"),
    (35, 70, "18K", "18K-22K", 75, "medium"),
    (70, 100, "14K", "14K-18K", 58, "high"),
    (100, 255, "Fake", "<14K", 20, "high"),
]

HALLMARK_PATTERNS = {
    "999": "24K",
    "916": "22K",
    "750": "18K",
    "585": "14K",
}

GOLD_PRICE_22K = 6230  # INR per gram (static offline reference)
GOLD_PRICE_BY_KARAT = {
    "24K": 6800,
    "22K": 6230,
    "18K": 5100,
    "14K": 3970,
}


# ═══════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════

def _resize_if_needed(img_bgr: np.ndarray, max_size: int = MAX_IMAGE_SIZE) -> np.ndarray:
    h, w = img_bgr.shape[:2]
    if max(h, w) <= max_size:
        return img_bgr
    scale = max_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)


def _safe_json_text(s: str) -> str:
    s = s.strip()
    if "```" in s:
        # Remove fenced code if OCR/text parsing returns it unexpectedly
        parts = s.split("```")
        if len(parts) >= 3:
            s = parts[1]
    return s.strip()


def _map_hallmark_to_purity(text: str) -> Optional[str]:
    text = (text or "").upper()
    for token, karat in HALLMARK_PATTERNS.items():
        if token in text:
            return karat
    if "BIS" in text and "916" in text:
        return "22K"
    if "BIS" in text and "750" in text:
        return "18K"
    if "BIS" in text and "585" in text:
        return "14K"
    return None


def _detect_text_tokens(text: str) -> List[str]:
    if not text:
        return []
    candidates = re.findall(r"[A-Z0-9]{3,}", text.upper())
    return sorted(set(candidates))


def _expected_weight_for_type(jtype: str) -> float:
    defaults = {"ring": 8, "chain": 15, "bangle": 20, "earring": 5, "coin": 10, "bar": 50}
    return defaults.get((jtype or "").lower(), 12)


def _weight_range(w: Optional[float], jtype: str) -> str:
    if w and w > 0:
        lo, hi = w * 0.85, w * 1.15
        return f"{lo:.1f}–{hi:.1f}g"
    mid = _expected_weight_for_type(jtype)
    return f"{mid * 0.7:.1f}–{mid * 1.3:.1f}g"


def _parse_image_upload_bytes(img_bytes: bytes) -> np.ndarray:
    np_arr = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise HTTPException(400, "Invalid image file")
    img_bgr = _resize_if_needed(img_bgr)
    return img_bgr


def _encode_image_to_b64(img_bgr: np.ndarray) -> str:
    _, buf = cv2.imencode(".jpg", img_bgr, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    return base64.b64encode(buf).decode("utf-8")


def _classify_luster(rg_mean: float) -> str:
    if rg_mean >= 180:
        return "high (rich gold glow)"
    if rg_mean >= 120:
        return "moderate"
    return "dull (possible alloy)"


def _extract_claimed_purity(karat_claim: Optional[str]) -> Optional[str]:
    if not karat_claim:
        return None
    claim = karat_claim.upper().replace(" ", "").strip()
    if claim in {"24K", "22K", "18K", "14K"}:
        return claim
    if "999" in claim:
        return "24K"
    if "916" in claim:
        return "22K"
    if "750" in claim:
        return "18K"
    if "585" in claim:
        return "14K"
    return None


# ═══════════════════════════════════════════════════════════════════
# OPTICAL ENGINE
# ═══════════════════════════════════════════════════════════════════

async def analyze_optical(img_bgr: np.ndarray) -> OpticalResult:
    # Stage 1: Dynamic normalization
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    i_white = float(np.percentile(gray, 97))

    # alpha = 1.0 - (Iw / 255 * Sens)
    alpha = 1.0 - ((i_white / 255.0) * SENSITIVITY)
    alpha = max(0.25, min(1.0, alpha))

    img_norm = np.clip(img_bgr.astype(np.float32) * alpha, 0, 255).astype(np.uint8)

    # Stage 2: signal conditioning
    img_filt = cv2.bilateralFilter(img_norm, 7, 50, 50)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # Stage 3: background retraction
    hsv = cv2.cvtColor(img_filt, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    mask = (saturation > 50).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    valid_pixels = int(np.sum(mask > 0))
    total_pixels = int(mask.size)

    # Stage 4: spectral partitioning
    blue = img_filt[:, :, 0].astype(np.float32)
    green = img_filt[:, :, 1].astype(np.float32)
    red = img_filt[:, :, 2].astype(np.float32)

    blue_masked = np.where((blue > 3) & (blue < 127) & (mask > 0), blue, np.nan)
    rg_masked = np.where(((red > 3) | (green > 3)) & (mask > 0), (red + green) / 2.0, np.nan)

    lb_mean = float(np.nanmean(blue_masked)) if not np.all(np.isnan(blue_masked)) else 128.0
    rg_mean = float(np.nanmean(rg_masked)) if not np.all(np.isnan(rg_masked)) else 128.0

    luster_profile = _classify_luster(rg_mean)

    # Stage 5: karat verdict
    karat_est, karat_range, base_score, plating_risk = "Unknown", "Unknown", 50, "high"
    for lo, hi, k_est, k_range, b_score, p_risk in KARAT_TABLE:
        if lo <= lb_mean < hi:
            karat_est, karat_range, base_score, plating_risk = k_est, k_range, b_score, p_risk
            break

    # Confidence score
    conf_score = (valid_pixels / total_pixels * 100) if total_pixels > 0 else 0.0
    conf_level = "green" if conf_score > 70 else ("yellow" if conf_score >= 40 else "red")

    # Edge diffusion / halo effect
    edges = cv2.Canny(img_filt, 50, 150)
    edge_dilated = cv2.dilate(edges, kernel, iterations=3)
    halo_pixels = int(np.sum(edge_dilated > 0)) - int(np.sum(edges > 0))
    edge_diffusion = halo_pixels / max(1, int(np.sum(edges > 0)))

    if edge_diffusion > 10:
        plating_risk = "high"
        base_score = min(base_score, 40)

    # Optional consistency bias:
    # Higher blue absorption + higher luster usually strengthens confidence in gold-like surface.
    luster_boost = 0.0
    if luster_profile.startswith("high"):
        luster_boost = 3.0
    elif luster_profile.startswith("moderate"):
        luster_boost = 1.0

    optical_score = float(np.clip(base_score * (conf_score / 100) ** 0.3 + luster_boost, 0, 100))

    return OpticalResult(
        lb_mean=round(lb_mean, 1),
        rg_mean=round(rg_mean, 1),
        confidence_score=round(conf_score, 1),
        karat_estimate=karat_est,
        karat_range=karat_range,
        optical_score=round(optical_score, 1),
        confidence_level=conf_level,
        plating_risk=plating_risk,
        alpha_scaling=round(alpha, 3),
        edge_diffusion_px=round(edge_diffusion, 2),
        luster_profile=luster_profile,
    )


# ═══════════════════════════════════════════════════════════════════
# OFFLINE HALLMARK ENGINE
# ═══════════════════════════════════════════════════════════════════

async def analyze_hallmark(hallmark_bytes: Optional[bytes]) -> HallmarkResult:
    if not hallmark_bytes:
        return HallmarkResult(
            hallmark_detected=False,
            hallmark_text=None,
            hallmark_confidence=0.0,
            hallmark_validity="missing",
            purity_from_hallmark=None,
            extracted_tokens=[],
            ocr_raw_text=None,
        )

    if pytesseract is None:
        # No OCR library installed, still offline but unavailable
        return HallmarkResult(
            hallmark_detected=False,
            hallmark_text=None,
            hallmark_confidence=0.0,
            hallmark_validity="unclear",
            purity_from_hallmark=None,
            extracted_tokens=[],
            ocr_raw_text=None,
        )

    try:
        img_bgr = _parse_image_upload_bytes(hallmark_bytes)

        # Preprocessing tailored for engraved/laser hallmark text
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Adaptive threshold helps under uneven lighting
        thr = cv2.adaptiveThreshold(
            gray,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            31,
            11,
        )

        # Some hallmark images read better inverted
        inv = cv2.bitwise_not(thr)

        # OCR on both variants
        config = "--psm 6 --oem 3"
        text_a = pytesseract.image_to_string(thr, config=config)
        text_b = pytesseract.image_to_string(inv, config=config)

        raw_text = _safe_json_text((text_a or "") + " " + (text_b or ""))
        raw_text = re.sub(r"\s+", " ", raw_text).strip()

        tokens = _detect_text_tokens(raw_text)
        purity = _map_hallmark_to_purity(raw_text)

        detected = bool(raw_text.strip())
        score = 0.0

        # Confidence estimation based on presence of expected hallmark tokens
        if "BIS" in raw_text.upper():
            score += 35
        if any(t in raw_text for t in ["916", "750", "585", "999"]):
            score += 40
        if re.search(r"\bHUID\b", raw_text.upper()):
            score += 15
        if len(tokens) >= 2:
            score += 10

        hallmark_confidence = float(np.clip(score, 0, 100))

        if not detected:
            validity = "missing"
        elif hallmark_confidence >= 60 and purity:
            validity = "valid"
        elif hallmark_confidence >= 35:
            validity = "suspicious"
        else:
            validity = "unclear"

        return HallmarkResult(
            hallmark_detected=detected,
            hallmark_text=raw_text[:120] if raw_text else None,
            hallmark_confidence=round(hallmark_confidence, 1),
            hallmark_validity=validity,
            purity_from_hallmark=purity,
            extracted_tokens=tokens,
            ocr_raw_text=raw_text if raw_text else None,
        )
    except Exception:
        return HallmarkResult(
            hallmark_detected=False,
            hallmark_text=None,
            hallmark_confidence=0.0,
            hallmark_validity="unclear",
            purity_from_hallmark=None,
            extracted_tokens=[],
            ocr_raw_text=None,
        )


# ═══════════════════════════════════════════════════════════════════
# ACOUSTIC ENGINE
# ═══════════════════════════════════════════════════════════════════

async def analyze_acoustic(audio_bytes: Optional[bytes]) -> Optional[AcousticResult]:
    if not audio_bytes:
        return None

    try:
        sr, data = wavfile.read(io.BytesIO(audio_bytes))
    except Exception:
        return None

    # Mono + normalize
    if data.ndim > 1:
        data = data.mean(axis=1)
    data = data.astype(np.float32)
    if data.size == 0:
        return None

    if np.max(np.abs(data)) > 0:
        data = data / np.max(np.abs(data))

    # SNR check
    noise_floor = float(np.percentile(np.abs(data), 10))
    signal_peak = float(np.percentile(np.abs(data), 90))
    snr_db = 20 * math.log10(signal_peak / max(noise_floor, 1e-10))
    flagged_noise = snr_db < 15.0

    # FFT
    n = min(len(data), 4096)
    if n < 128:
        return None

    chunk = data[:n] * np.hanning(n)
    spectrum = np.abs(fft(chunk))[: n // 2]
    freqs = fftfreq(n, 1 / sr)[: n // 2]

    # Fundamental frequency
    mask = (freqs >= 1000) & (freqs <= 6000)
    if mask.any():
        sub = spectrum.copy()
        sub[~mask] = 0
        peaks, props = find_peaks(sub, height=sub.max() * 0.15, distance=20)
        if len(peaks) > 0:
            best_peak_idx = peaks[np.argmax(props["peak_heights"])]
            f0 = float(freqs[best_peak_idx])
        else:
            f0 = 0.0
    else:
        f0 = 0.0

    # T60 decay time (approx)
    frame = max(1, int(sr * 0.01))
    rms_env = [np.sqrt(np.mean(data[i:i + frame] ** 2)) for i in range(0, len(data) - frame, frame)]
    if rms_env:
        peak_rms = max(rms_env)
        thresh = peak_rms * 0.001
        t60_idx = next((i for i, v in reversed(list(enumerate(rms_env))) if v > thresh), len(rms_env))
        t60 = float(t60_idx * 0.01)
    else:
        t60 = 0.0

    # Q factor
    if f0 > 0:
        f0_bin = int(np.argmin(np.abs(freqs - f0)))
        half_max = spectrum[f0_bin] * 0.707 if spectrum[f0_bin] > 0 else 0
        left = next((i for i in range(f0_bin, 0, -1) if spectrum[i] < half_max), 0)
        right = next((i for i in range(f0_bin, len(spectrum)) if spectrum[i] < half_max), f0_bin)
        bandwidth = max(freqs[right] - freqs[left], 1.0)
        q_factor = float(f0 / bandwidth)
    else:
        q_factor = 0.0

    # Harmonic ratio
    harmonic_energy = 0.0
    total_energy = float(np.sum(spectrum ** 2)) + 1e-10
    for h in range(2, 6):
        hf = f0 * h
        if hf < freqs[-1] and hf > 0:
            hi_bin = int(np.argmin(np.abs(freqs - hf)))
            window = max(5, int(50 / (sr / n)))
            lo_b = max(0, hi_bin - window)
            hi_b = min(len(spectrum), hi_bin + window)
            harmonic_energy += float(np.sum(spectrum[lo_b:hi_b] ** 2))
    harmonic_ratio = harmonic_energy / total_energy

    # Scoring
    score = 0.0
    in_f0 = 2500 <= f0 <= 4500
    in_t60 = 1.5 <= t60 <= 3.0

    if in_f0:
        score += 35
    elif f0 > 0:
        score += 10

    if in_t60:
        score += 40
    elif t60 > 0.8:
        score += 15

    if q_factor > 30:
        score += 15
    elif q_factor > 10:
        score += 7

    if harmonic_ratio > 0.15:
        score += 10

    if t60 >= 1.5:
        decay_cat = "long sing"
    elif t60 >= 0.5:
        decay_cat = "moderate"
    else:
        decay_cat = "dull thud"

    if score >= 70:
        mat = "22K–24K gold"
    elif score >= 45:
        mat = "18K gold / alloy"
    else:
        mat = "base metal / plated"

    conf = "green" if score > 70 and not flagged_noise else ("yellow" if score > 45 else "red")

    return AcousticResult(
        f0_hz=round(f0, 1),
        t60_seconds=round(t60, 3),
        q_factor=round(q_factor, 2),
        harmonic_ratio=round(harmonic_ratio, 4),
        snr_db=round(snr_db, 1),
        audio_score=round(score, 1),
        material_match=mat,
        decay_category=decay_cat,
        confidence_level=conf,
        flagged_noise=flagged_noise,
    )


# ═══════════════════════════════════════════════════════════════════
# CONSENSUS ENGINE
# ═══════════════════════════════════════════════════════════════════

async def build_consensus(
    optical: OpticalResult,
    hallmark: HallmarkResult,
    acoustic: Optional[AcousticResult],
    jewelry_type: str,
    weight_g: Optional[float],
    karat_claim: Optional[str] = None,
    has_purchase_bill: bool = False,
) -> tuple[ConsensusResult, XAIResult]:

    s_opt = optical.optical_score
    s_aco = acoustic.audio_score if acoustic else s_opt * 0.9
    s_hmk = hallmark.hallmark_confidence if hallmark.hallmark_detected else 0.0

    # Combine signals; redistributes weight if hallmark absent
    if hallmark.hallmark_detected:
        final = 0.35 * s_opt + 0.30 * s_aco + 0.35 * s_hmk
    else:
        final = 0.45 * s_opt + 0.40 * s_aco + 0.15 * s_hmk

    delta = abs(s_opt - s_aco)

    penalties: list[str] = []

    if optical.confidence_level == "red":
        final *= 0.80
        penalties.append("Low optical confidence — score penalized")

    if acoustic and acoustic.flagged_noise:
        final *= 0.85
        penalties.append("Ambient audio noise detected — score penalized")

    if hallmark.hallmark_validity in {"suspicious", "unclear"}:
        final *= 0.90
        penalties.append("Hallmark uncertainty — score penalized")

    if hallmark.hallmark_validity == "missing":
        final *= 0.92
        penalties.append("Hallmark missing — score slightly penalized")

    if has_purchase_bill:
        # Trust boost, but not overly strong
        final *= 1.03
        penalties.append("Purchase bill present — slight trust boost applied")

    claimed_purity = _extract_claimed_purity(karat_claim)
    if claimed_purity:
        # Penalize strong mismatch between claim and computed purity
        if claimed_purity == "22K" and optical.karat_estimate in {"14K", "18K", "Fake"}:
            final *= 0.80
            penalties.append("Claimed 22K conflicts with optical purity")
        elif claimed_purity == "18K" and optical.karat_estimate in {"24K", "22K"}:
            final *= 0.90
            penalties.append("Claimed 18K conflicts with optical purity")
        elif claimed_purity == "14K" and optical.karat_estimate in {"24K", "22K"}:
            final *= 0.85
            penalties.append("Claimed 14K conflicts with optical purity")

    if hallmark.purity_from_hallmark:
        hm = hallmark.purity_from_hallmark
        if hm == "22K" and optical.karat_estimate in {"14K", "18K", "Fake"}:
            final *= 0.75
            penalties.append("Optical-hallmark mismatch: hallmark claims 22K but optical is lower")
        elif hm == "18K" and optical.karat_estimate in {"24K", "22K"}:
            final *= 0.85
            penalties.append("Optical-hallmark mismatch: hallmark claims 18K but optical is higher")
        elif hm == "14K" and optical.karat_estimate in {"24K", "22K"}:
            final *= 0.80
            penalties.append("Optical-hallmark mismatch: hallmark claims 14K but optical is higher")

    if delta > 40:
        final = min(final, 48)
        penalties.append(f"Severe optical-acoustic conflict (Δ={delta:.0f}) — score capped")

    final = float(np.clip(final, 0, 100))

    if final >= 85:
        risk, rec, ltv = "low", "pre_approve", 0.75
    elif final >= 50:
        risk, rec, ltv = "medium", "needs_verification", 0.50
    else:
        risk, rec, ltv = "high", "reject", 0.0

    w_range = _weight_range(weight_g, jewelry_type)
    purity_band = optical.karat_range

    # Valuation
    price_key = "22K"
    if "24K" in purity_band:
        price_key = "24K"
    elif "18K" in purity_band:
        price_key = "18K"
    elif "14K" in purity_band:
        price_key = "14K"

    price_pg = GOLD_PRICE_BY_KARAT[price_key]
    est_val = weight_g * price_pg if weight_g and weight_g > 0 else None
    max_loan = est_val * ltv if est_val and ltv > 0 else None

    consensus = ConsensusResult(
        final_score=round(final, 1),
        delta_integrity=round(delta, 1),
        risk_level=risk,
        recommendation=rec,
        ltv_percent=ltv * 100 if ltv else None,
        max_loan_inr=round(max_loan, 0) if max_loan else None,
        weight_range_g=w_range,
        purity_band=purity_band,
        estimated_value_inr=round(est_val, 0) if est_val else None,
    )

    # Fraud flags
    fraud_flags: list[str] = []
    if delta > 40:
        fraud_flags.append(f"Severe conflict: Optical={s_opt:.0f} vs Acoustic={s_aco:.0f} (Δ={delta:.0f})")
    if optical.plating_risk == "high":
        fraud_flags.append(f"High plating risk: edge diffusion={optical.edge_diffusion_px}px")
    if hallmark.hallmark_validity == "missing":
        fraud_flags.append("Hallmark missing")
    if hallmark.hallmark_validity in {"suspicious", "unclear"}:
        fraud_flags.append("Hallmark OCR is suspicious or unclear")
    if hallmark.purity_from_hallmark and optical.karat_estimate != "Unknown":
        if hallmark.purity_from_hallmark == "22K" and optical.karat_estimate in {"14K", "18K", "Fake"}:
            fraud_flags.append("Hallmark says 22K but optical purity is lower")
        if hallmark.purity_from_hallmark == "18K" and optical.karat_estimate == "24K":
            fraud_flags.append("Hallmark says 18K but optical suggests much higher purity")
    if acoustic and acoustic.t60_seconds < 0.5 and acoustic.t60_seconds > 0:
        fraud_flags.append(f"T60={acoustic.t60_seconds:.2f}s is too short for gold-like resonance")
    if acoustic and acoustic.snr_db < 15:
        fraud_flags.append(f"Audio SNR too low ({acoustic.snr_db:.1f} dB)")
    if claimed_purity and optical.karat_estimate != "Unknown":
        if claimed_purity == "22K" and optical.karat_estimate in {"14K", "18K", "Fake"}:
            fraud_flags.append("Claimed 22K conflicts with optical estimate")
        if claimed_purity == "18K" and optical.karat_estimate in {"24K", "22K"}:
            fraud_flags.append("Claimed 18K conflicts with optical estimate")

    # Trust factors
    trust_factors: list[str] = []
    if hallmark.hallmark_validity == "valid":
        trust_factors.append(f"Hallmark validated ({hallmark.hallmark_text or 'detected'})")
    if optical.confidence_level == "green":
        trust_factors.append(f"High optical confidence ({optical.confidence_score:.0f}%)")
    if acoustic and acoustic.t60_seconds >= 1.5:
        trust_factors.append(f"T60={acoustic.t60_seconds:.2f}s — long sing resonance")
    if delta < 10:
        trust_factors.append(f"Optical-acoustic consensus strong (Δ={delta:.1f})")
    if hallmark.purity_from_hallmark:
        trust_factors.append(f"Hallmark purity inferred as {hallmark.purity_from_hallmark}")
    if has_purchase_bill:
        trust_factors.append("Purchase bill present")
    if claimed_purity:
        trust_factors.append(f"Claimed purity: {claimed_purity}")

    if rec == "pre_approve":
        narrative = (
            f"Pre-Approved. Final score {final:.0f}/100. "
            f"Optical score {s_opt:.0f}/100 suggests {optical.karat_estimate} (L_B={optical.lb_mean:.1f}, RG={optical.rg_mean:.1f}). "
            f"{'Hallmark detected: ' + (hallmark.hallmark_text or 'present') + '. ' if hallmark.hallmark_detected else 'No hallmark input. '}"
            f"{'Acoustic score ' + str(round(s_aco, 0)) + '/100 indicates gold-like resonance. ' if acoustic else 'No audio provided. '}"
            f"Estimated value ₹{int(est_val):,} and max loan ₹{int(max_loan):,} at 75% LTV." if max_loan else
            f"Estimated value unavailable due to missing weight."
        )
    elif rec == "needs_verification":
        narrative = (
            f"Needs Verification. Final score {final:.0f}/100. "
            f"Optical: {optical.karat_estimate} ({s_opt:.0f}/100). "
            f"{'Hallmark: ' + (hallmark.hallmark_text or hallmark.hallmark_validity) + '. ' if hallmark.hallmark_detected else 'Hallmark absent or unclear. '}"
            f"{'Acoustic: ' + acoustic.material_match + ' (' + str(round(s_aco, 0)) + '/100). ' if acoustic else ''}"
            f"Conflict delta {delta:.0f}. Manual appraisal or retake recommended."
        )
    else:
        conflict_str = f"Optical-acoustic conflict Δ={delta:.0f}" if delta > 40 else "Low confidence across modalities"
        narrative = (
            f"Rejected. Final score {final:.0f}/100. {conflict_str}. "
            f"Fraud indicators: {', '.join(fraud_flags[:2]) if fraud_flags else 'insufficient signal quality'}. "
            f"Item should not proceed without physical verification."
        )

    xai = XAIResult(
        narrative=narrative,
        optical_confidence=optical.confidence_level,
        acoustic_confidence=acoustic.confidence_level if acoustic else "n/a",
        hallmark_confidence=hallmark.hallmark_validity,
        overall_confidence="green" if final >= 85 else ("yellow" if final >= 50 else "red"),
        fraud_flags=fraud_flags,
        trust_factors=trust_factors,
        penalty_notes=penalties,
    )

    return consensus, xai


# ═══════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.post("/api/assess", response_model=AssessmentResponse)
async def assess(
    request: Request,
    image: UploadFile = File(...),
    hallmark: Optional[UploadFile] = File(None),
    audio: Optional[UploadFile] = File(None),
    jewelry_type: str = Form("ring"),
    weight_g: Optional[float] = Form(None),
    karat_claim: Optional[str] = Form(None),
    has_purchase_bill: bool = Form(False),
):
    start = time.time()

    # Rate limit
    client_ip = request.client.host if request.client else "unknown"
    if not check_rate_limit(client_ip, limit=RATE_LIMIT_PER_MINUTE, window=RATE_LIMIT_WINDOW_SECONDS):
        raise HTTPException(429, "Rate limit exceeded. Try again later.")

    session_id = str(uuid.uuid4())[:8]

    # Read and decode image
    img_bytes = await image.read()
    img_bgr = _parse_image_upload_bytes(img_bytes)
    img_b64 = _encode_image_to_b64(img_bgr)  # kept for future caching/debug parity

    # Read optional hallmark image
    hallmark_bytes = await hallmark.read() if hallmark else None

    # Read optional audio
    audio_bytes = await audio.read() if audio else None

    # Run analyses concurrently where possible
    optical_task = analyze_optical(img_bgr)
    hallmark_task = analyze_hallmark(hallmark_bytes)
    acoustic_task = analyze_acoustic(audio_bytes)

    optical_result, hallmark_result, acoustic_result = await asyncio.gather(
        optical_task,
        hallmark_task,
        acoustic_task,
    )

    # Consensus + XAI
    consensus, xai = await build_consensus(
        optical=optical_result,
        hallmark=hallmark_result,
        acoustic=acoustic_result,
        jewelry_type=jewelry_type,
        weight_g=weight_g,
        karat_claim=karat_claim,
        has_purchase_bill=has_purchase_bill,
    )

    processing_time_ms = (time.time() - start) * 1000.0

    return AssessmentResponse(
        session_id=session_id,
        timestamp=time.time(),
        optical=optical_result,
        hallmark=hallmark_result,
        acoustic=acoustic_result,
        consensus=consensus,
        xai=xai,
        processing_time_ms=round(processing_time_ms, 1),
    )


@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "service": "Aethra Gold Assessment",
        "version": "3.1.0",
        "offline_mode": True,
        "ocr_available": pytesseract is not None,
        "dynamic_normalization": True,
        "blue_red_green_channel_logic": True,
    }


@app.get("/api/gold-price")
async def gold_price():
    return {
        "price_22k_per_g": GOLD_PRICE_22K,
        "currency": "INR",
        "updated": time.time(),
        "offline_reference": True,
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
        },
    )