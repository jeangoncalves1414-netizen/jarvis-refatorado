"""Local speech/overlap gate; local speaker labels are not person identities."""
from pathlib import Path
import hashlib
import io
import tarfile
import threading
from urllib.request import urlopen

import numpy as np

MODEL_PATH = Path('data/models/speaker_segmentation.onnx')
MODEL_SHA256 = '220ad67ca923bef2fa91f2390c786097bf305bceb5e261d4af67b38e938e1079'
ARCHIVE_SHA256 = '24615ee884c897d9d2ba09bb4d30da6bb1b15e685065962db5b02e76e4996488'
MODEL_URL = ('https://github.com/k2-fsa/sherpa-onnx/releases/download/'
             'speaker-segmentation-models/sherpa-onnx-pyannote-segmentation-3-0.tar.bz2')
MAPPING = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1],
                    [1, 1, 0], [1, 0, 1], [0, 1, 1]])
STEP = 270 / 16000


class VoiceSegmentationEngine:
    def __init__(self, model_path=MODEL_PATH):
        self.model_path = Path(model_path)
        self._session = None
        self._lock = threading.RLock()

    def install(self):
        with self._lock:
            if self.model_path.is_file() and hashlib.sha256(self.model_path.read_bytes()).hexdigest() == MODEL_SHA256:
                return
            with urlopen(MODEL_URL, timeout=90) as response:
                archive = response.read(10_000_001)
            if hashlib.sha256(archive).hexdigest() != ARCHIVE_SHA256:
                raise ValueError('O download da segmentação de voz não passou na verificação de integridade.')
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:bz2') as bundle:
                # Read only the named model; never extract paths from the archive.
                data = bundle.extractfile('sherpa-onnx-pyannote-segmentation-3-0/model.onnx').read()
            if hashlib.sha256(data).hexdigest() != MODEL_SHA256:
                raise ValueError('Modelo de segmentação inválido.')
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.model_path.with_suffix('.download')
            temporary.write_bytes(data)
            temporary.replace(self.model_path)
            self._session = None

    def _get_session(self):
        with self._lock:
            if self._session is None:
                if not self.model_path.is_file():
                    raise ValueError('Prepare novamente o modelo de voz para instalar a segmentação local.')
                if hashlib.sha256(self.model_path.read_bytes()).hexdigest() != MODEL_SHA256:
                    raise ValueError('Modelo de segmentação corrompido. Prepare novamente o modelo de voz.')
                import onnxruntime as ort
                options = ort.SessionOptions()
                options.intra_op_num_threads = 1
                options.inter_op_num_threads = 1
                self._session = ort.InferenceSession(str(self.model_path), options, providers=['CPUExecutionProvider'])
            return self._session

    def analyze(self, samples):
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim != 1 or not np.isfinite(samples).all() or len(samples) > 16000 * 60:
            raise ValueError('Use uma amostra mono de voz de até 60 segundos.')
        session = self._get_session()
        speech_seconds = overlap_seconds = 0.0
        multiple_speakers = False
        segments = []
        # Overlapping windows catch speaker changes at chunk boundaries. Their
        # labels cannot be compared across windows without speaker embeddings.
        for start in range(0, max(1, len(samples) - 80000), 80000):
            chunk = samples[start:start + 160000]
            padded = np.pad(chunk, (0, 160000 - len(chunk)))
            scores = session.run(['y'], {'x': padded[None, None, :]})[0][0]
            valid = max(0, min(len(scores), (len(chunk) - 991) // 270 + 1))
            if not np.isfinite(scores).all():
                raise ValueError('A segmentação de voz retornou um resultado inválido.')
            labels = MAPPING[scores[:valid].argmax(axis=-1)]
            durations = labels.sum(axis=0) * STEP
            multiple_speakers |= int(np.count_nonzero(durations >= 0.2)) > 1
            # Max over windows avoids counting overlapping windows twice.
            speech_seconds = max(speech_seconds, float(np.count_nonzero(labels.sum(axis=1)) * STEP))
            overlap_seconds = max(overlap_seconds, float(np.count_nonzero(labels.sum(axis=1) > 1) * STEP))
            # Each overlapping window owns its central interval. Local speaker
            # indices are never carried into the next window as person identities.
            lower = 0 if start == 0 else start / 16000 + 2.5
            upper = min(len(samples) / 16000, start / 16000 + 7.5) if start + 160000 < len(samples) else len(samples) / 16000
            active = labels.sum(axis=1)
            classes = np.where(active > 1, -2, np.where(active == 1, labels.argmax(axis=1), -1))
            begin = 0
            for end in range(1, len(classes) + 1):
                if end < len(classes) and classes[end] == classes[begin]:
                    continue
                left = max(lower, start / 16000 + begin * STEP)
                right = min(upper, start / 16000 + end * STEP)
                if classes[begin] != -1 and right - left >= .12:
                    segments.append({'start': left, 'end': right, 'local_speaker': f'{start}:{classes[begin]}',
                                     'overlap': bool(classes[begin] == -2)})
                begin = end
        return {'speech_seconds': speech_seconds, 'overlap_seconds': overlap_seconds,
                'multiple_speakers': bool(multiple_speakers), 'segments': segments}


engine = VoiceSegmentationEngine()
