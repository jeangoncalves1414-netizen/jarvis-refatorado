"""Instala o modelo oficial fixado para uso posterior completamente offline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.storage.vector.multilingual_embedding import MODEL_ID, MODEL_DIR, REVISION


if __name__ == "__main__":
    from huggingface_hub import hf_hub_download
    for filename in ("tokenizer.json", "onnx/model.onnx"):
        hf_hub_download(MODEL_ID, filename, revision=REVISION, local_dir=MODEL_DIR)
    print(f"Modelo pronto para uso offline: {MODEL_DIR}")
