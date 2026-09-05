import atexit
from functools import lru_cache

from qdrant_client import QdrantClient, models

from assistant.config import settings

COLLECTION = "hospital_pages"
DENSE = "dense"
SPARSE = "sparse"

# Served by fastembed as ONNX, so nothing here pulls in PyTorch.
DENSE_MODEL = "BAAI/bge-small-en-v1.5"
SPARSE_MODEL = "Qdrant/bm25"
# A cross-encoder reads query and passage together, so it ranks better than
# the bi-encoder that retrieved them. This one is ONNX, like the others.
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
DENSE_SIZE = 384


@lru_cache(maxsize=1)
def client() -> QdrantClient:
    settings.QDRANT_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = QdrantClient(path=str(settings.QDRANT_PATH))
    # Closed here rather than in __del__, which runs after the import system
    # has gone and raises on the way out.
    atexit.register(connection.close)
    return connection


def ensure_collection() -> None:
    connection = client()

    if connection.collection_exists(COLLECTION):
        return

    connection.create_collection(
        collection_name=COLLECTION,
        vectors_config={
            DENSE: models.VectorParams(size=DENSE_SIZE, distance=models.Distance.COSINE)
        },
        sparse_vectors_config={SPARSE: models.SparseVectorParams()},
    )
