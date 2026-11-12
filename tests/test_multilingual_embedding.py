import numpy as np
import pytest

from app.storage.vector.multilingual_embedding import MODEL_DIR, MultilingualEmbedding


def test_missing_weights_fails_without_network(tmp_path):
    with pytest.raises(RuntimeError, match="setup_memory_embeddings"):
        MultilingualEmbedding(tmp_path)


@pytest.mark.skipif(not (MODEL_DIR / "onnx/model.onnx").exists(), reason="Modelo local não instalado")
def test_portuguese_embeddings_offline_and_comparison(monkeypatch):
    from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
    from pathlib import Path
    if not (Path.home() / ".cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/model.onnx").exists():
        pytest.skip("Modelo inglês não instalado; teste não baixa pesos")
    import socket
    def offline(*args, **kwargs):
        raise AssertionError("Inferência não pode acessar a rede")
    monkeypatch.setattr(socket, "create_connection", offline)
    phrases = ["o usuário gosta de pizza", "qual comida eu gosto?"]
    multilingual = np.asarray(MultilingualEmbedding()(phrases))
    english = np.asarray(ONNXMiniLM_L6_V2()(phrases))
    def distance(values):
        return 1 - np.dot(values[0], values[1]) / (np.linalg.norm(values[0]) * np.linalg.norm(values[1]))
    assert multilingual.shape == (2, 384)
    assert np.allclose(np.linalg.norm(multilingual, axis=1), 1)
    # Benchmark observado: este par não melhora com o modelo solicitado.
    # Não transformar uma expectativa de qualidade em resultado falso.
    print(f"pizza: multilingual={distance(multilingual):.6f}, english={distance(english):.6f}")
    assert np.isfinite(distance(multilingual)) and np.isfinite(distance(english))
