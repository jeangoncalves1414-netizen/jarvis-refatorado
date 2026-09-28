"""
QR Reader Service — Lê QR Codes de:
  - Captura de tela (mss + pyzbar/opencv)
  - Webcam (opencv)
  - Dados de imagem base64 enviados pelo frontend (câmera do browser)

Dependências opcionais:
    pip install pyzbar opencv-python pillow mss
    (No Windows, pyzbar também precisa da DLL: pip install pyzbar[pure])
"""
from __future__ import annotations

import base64
import io
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ── Dependency detection ─────────────────────────────────────────────────────
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from pyzbar import pyzbar  # type: ignore
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False

try:
    import cv2  # type: ignore
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    import mss  # type: ignore
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

QR_AVAILABLE = PIL_AVAILABLE and (PYZBAR_AVAILABLE or OPENCV_AVAILABLE)


@dataclass
class QRResult:
    ok: bool
    codes: list[dict[str, Any]] = field(default_factory=list)
    source: str = ""
    error: str = ""
    capture_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "codes": self.codes,
            "source": self.source,
            "error": self.error,
            "capture_time_ms": self.capture_time_ms,
            "count": len(self.codes),
        }


class QRReaderService:
    """Serviço de leitura de QR Code a partir de tela, câmera ou imagem base64."""

    # ── Internal decoders ──────────────────────────────────────────────────

    def _decode_pil(self, pil_img: "PILImage.Image") -> list[dict[str, Any]]:
        """Tenta decodificar com pyzbar primeiro, fallback para OpenCV."""
        codes: list[dict[str, Any]] = []

        if PYZBAR_AVAILABLE:
            try:
                decoded = pyzbar.decode(pil_img)
                for obj in decoded:
                    codes.append({
                        "data": obj.data.decode("utf-8", errors="replace"),
                        "type": obj.type,
                        "rect": {
                            "left": obj.rect.left,
                            "top": obj.rect.top,
                            "width": obj.rect.width,
                            "height": obj.rect.height,
                        },
                    })
                if codes:
                    return codes
            except Exception as e:
                logger.debug("pyzbar decode error: %s", e)

        # Fallback: OpenCV QR detector
        if OPENCV_AVAILABLE:
            try:
                import numpy as np
                img_np = np.array(pil_img.convert("RGB"))
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                detector = cv2.QRCodeDetector()
                data, pts, _ = detector.detectAndDecode(img_bgr)
                if data:
                    rect: dict[str, Any] = {}
                    if pts is not None:
                        pts_list = pts[0].tolist()
                        xs = [p[0] for p in pts_list]
                        ys = [p[1] for p in pts_list]
                        rect = {
                            "left": int(min(xs)),
                            "top": int(min(ys)),
                            "width": int(max(xs) - min(xs)),
                            "height": int(max(ys) - min(ys)),
                        }
                    codes.append({"data": data, "type": "QRCODE", "rect": rect})
            except Exception as e:
                logger.debug("OpenCV QR decode error: %s", e)

        return codes

    # ── Public methods ─────────────────────────────────────────────────────

    def read_from_screen(self, monitor: int = 0) -> QRResult:
        """
        Captura a tela inteira (ou um monitor específico) e procura QR codes.
        monitor=0 → todos os monitores combinados; monitor=1,2,... → monitor específico.
        """
        t0 = time.time()
        if not QR_AVAILABLE:
            return QRResult(ok=False, error="Dependências de QR não disponíveis (pyzbar/opencv/PIL).", source="screen")
        if not MSS_AVAILABLE:
            return QRResult(ok=False, error="mss não disponível para captura de tela.", source="screen")
        if not PIL_AVAILABLE:
            return QRResult(ok=False, error="Pillow não disponível.", source="screen")

        try:
            import mss as _mss
            with _mss.MSS() as sct:
                monitors = sct.monitors
                # monitor 0 = all screens combined; 1+ = specific
                if monitor < len(monitors):
                    mon = monitors[monitor]
                else:
                    mon = monitors[0]
                screenshot = sct.grab(mon)
                pil_img = PILImage.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

            codes = self._decode_pil(pil_img)
            elapsed = (time.time() - t0) * 1000
            return QRResult(
                ok=True,
                codes=codes,
                source="screen",
                capture_time_ms=round(elapsed, 1),
            )
        except Exception as exc:
            logger.error("QR screen capture error: %s", exc)
            return QRResult(ok=False, error=str(exc), source="screen")

    def read_from_camera(self, camera_index: int = 0, timeout_s: float = 5.0) -> QRResult:
        """
        Abre a webcam e tenta decodificar QR codes por até timeout_s segundos.
        """
        t0 = time.time()
        if not OPENCV_AVAILABLE:
            return QRResult(ok=False, error="OpenCV não disponível (pip install opencv-python).", source="camera")

        cap = None
        try:
            cap = cv2.VideoCapture(camera_index)
            if not cap.isOpened():
                return QRResult(ok=False, error=f"Câmera {camera_index} não encontrada ou em uso.", source="camera")

            detector = cv2.QRCodeDetector()
            deadline = t0 + timeout_s

            while time.time() < deadline:
                ret, frame = cap.read()
                if not ret:
                    break

                data, pts, _ = detector.detectAndDecode(frame)
                if data:
                    rect: dict[str, Any] = {}
                    if pts is not None:
                        pts_list = pts[0].tolist()
                        xs = [p[0] for p in pts_list]
                        ys = [p[1] for p in pts_list]
                        rect = {
                            "left": int(min(xs)),
                            "top": int(min(ys)),
                            "width": int(max(xs) - min(xs)),
                            "height": int(max(ys) - min(ys)),
                        }
                    elapsed = (time.time() - t0) * 1000
                    return QRResult(
                        ok=True,
                        codes=[{"data": data, "type": "QRCODE", "rect": rect}],
                        source="camera",
                        capture_time_ms=round(elapsed, 1),
                    )

            elapsed = (time.time() - t0) * 1000
            return QRResult(
                ok=True,
                codes=[],
                source="camera",
                error="Nenhum QR Code encontrado dentro do tempo limite.",
                capture_time_ms=round(elapsed, 1),
            )
        except Exception as exc:
            logger.error("QR camera error: %s", exc)
            return QRResult(ok=False, error=str(exc), source="camera")
        finally:
            if cap is not None:
                cap.release()

    def read_from_base64(self, image_b64: str, source_label: str = "browser") -> QRResult:
        """
        Decodifica QR a partir de uma imagem base64 enviada pelo frontend
        (útil para câmera do browser via canvas.toDataURL).
        """
        t0 = time.time()
        if not PIL_AVAILABLE:
            return QRResult(ok=False, error="Pillow não disponível.", source=source_label)

        try:
            # Remove data URI prefix if present
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]

            img_bytes = base64.b64decode(image_b64)
            pil_img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            codes = self._decode_pil(pil_img)
            elapsed = (time.time() - t0) * 1000
            return QRResult(
                ok=True,
                codes=codes,
                source=source_label,
                capture_time_ms=round(elapsed, 1),
            )
        except Exception as exc:
            logger.error("QR base64 decode error: %s", exc)
            return QRResult(ok=False, error=str(exc), source=source_label)

    @staticmethod
    def availability() -> dict[str, bool]:
        return {
            "pyzbar": PYZBAR_AVAILABLE,
            "opencv": OPENCV_AVAILABLE,
            "pil": PIL_AVAILABLE,
            "mss": MSS_AVAILABLE,
            "ready": QR_AVAILABLE,
        }
