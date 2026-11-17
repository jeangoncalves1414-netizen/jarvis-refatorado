"""Local YuNet/SFace inference; no images are uploaded. MIT/Apache-2.0 models."""
from pathlib import Path
import hashlib
import threading
import requests

REVISION = '48b10fa505aeb51fbd127fc60a5c660040e823b7'
MODELS = {
    'face_detection_yunet_2023mar.onnx': ('face_detection_yunet', '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),
    'face_recognition_sface_2021dec.onnx': ('face_recognition_sface', '0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79'),
}


class FaceIdentityEngine:
    def __init__(self, directory=Path('data/models/faces')):
        self.directory = directory
        self.lock = threading.RLock()
        self.detector = self.recognizer = None

    def status(self):
        return {'ok': True, 'model_id': 'sface-2021dec',
                'ready': all((self.directory / name).is_file() for name in MODELS)}

    def install(self):
        with self.lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            for name, (folder, digest) in MODELS.items():
                target = self.directory / name
                if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
                    continue
                temporary = target.with_suffix('.download')
                try:
                    url = f'https://media.githubusercontent.com/media/opencv/opencv_zoo/{REVISION}/models/{folder}/{name}'
                    with requests.get(url, stream=True, timeout=(10, 90)) as response:
                        response.raise_for_status()
                        with temporary.open('wb') as output:
                            for chunk in response.iter_content(1024 * 1024):
                                output.write(chunk)
                    if hashlib.sha256(temporary.read_bytes()).hexdigest() != digest:
                        raise ValueError('Modelo facial inválido: checksum diferente.')
                    temporary.replace(target)
                finally:
                    temporary.unlink(missing_ok=True)
            return self.status()

    def extract(self, raw):
        import cv2
        import numpy as np
        if not self.status()['ready']:
            raise ValueError('Prepare o modelo facial local na página Identidade.')
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError('Imagem inválida.')
        if max(image.shape[:2]) > 1280:
            scale = 1280 / max(image.shape[:2])
            image = cv2.resize(image, None, fx=scale, fy=scale)
        with self.lock:
            if self.detector is None:
                names = list(MODELS)
                self.detector = cv2.FaceDetectorYN.create(str(self.directory / names[0]), '', (320, 320), 0.9)
                self.recognizer = cv2.FaceRecognizerSF.create(str(self.directory / names[1]), '')
            self.detector.setInputSize((image.shape[1], image.shape[0]))
            _, faces = self.detector.detect(image)
            result = []
            for face in ([] if faces is None else faces):
                if min(face[2:4]) < 80:
                    continue
                aligned = self.recognizer.alignCrop(image, face)
                vector = self.recognizer.feature(aligned).flatten()
                norm = np.linalg.norm(vector)
                if not np.isfinite(vector).all() or norm <= 0:
                    continue
                # Signed displacement normalized by eye spacing. Used as a
                # relative pose cue across captures, never as a yaw angle.
                eye_a, eye_b, nose = face[4:10].reshape(3, 2)
                baseline = eye_b - eye_a
                pose = float(np.dot(nose - (eye_a + eye_b) / 2, baseline) / max(np.dot(baseline, baseline), 1))
                result.append({'box': [float(v) for v in face[:4]], 'embedding': (vector / norm).tolist(), 'pose': pose})
            return result

    def embed(self, raw):
        faces = self.extract(raw)
        if len(faces) != 1:
            raise ValueError('Mostre exatamente um rosto próximo e visível para cadastrar ou verificar.')
        return faces[0]['embedding']


engine = FaceIdentityEngine()
