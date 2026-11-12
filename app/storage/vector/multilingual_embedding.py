"""Embeddings ONNX locais; instalação explícita, nenhuma rede durante a inferência."""
from pathlib import Path

import numpy as np
from chromadb.api.types import Documents, EmbeddingFunction

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MODEL_DIR = Path(__file__).resolve().parents[3] / "data/models/multilingual-minilm"


class MultilingualEmbedding(EmbeddingFunction[Documents]):
    def __init__(self, model_dir=None):
        from tokenizers import Tokenizer
        import onnxruntime as ort

        self.model_dir = Path(model_dir or MODEL_DIR)
        if not (self.model_dir / "onnx/model.onnx").is_file():
            raise RuntimeError("Instale o modelo local: python scripts/setup_memory_embeddings.py")
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=128)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        self.session = ort.InferenceSession(str(self.model_dir / "onnx/model.onnx"),
                                           providers=["CPUExecutionProvider"])

    def __call__(self, input: Documents):
        result = []
        for start in range(0, len(input), 32):
            encoded = self.tokenizer.encode_batch(list(input[start:start + 32]))
            arrays = {"input_ids": np.asarray([e.ids for e in encoded], dtype=np.int64),
                      "attention_mask": np.asarray([e.attention_mask for e in encoded], dtype=np.int64),
                      "token_type_ids": np.asarray([e.type_ids for e in encoded], dtype=np.int64)}
            output = self.session.run(None, {i.name: arrays[i.name] for i in self.session.get_inputs()})[0]
            mask = arrays["attention_mask"][..., None]
            pooled = (output * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12)
            result.extend(pooled.astype(np.float32))
        return result

    @staticmethod
    def name():
        return "jarvis-multilingual-minilm-onnx"

    def default_space(self):
        return "cosine"

    def get_config(self):
        return {"revision": REVISION}

    @staticmethod
    def build_from_config(config):
        if config.get("revision") != REVISION:
            raise ValueError("Revisão de embedding incompatível; reindexação necessária.")
        return MultilingualEmbedding()
