"""BM25-style sparse vectors for hybrid search — pure, no Qdrant client involved.

Documents carry BM25 term-frequency weights and queries carry 1.0 per distinct
token; Qdrant applies the IDF factor server-side (`Modifier.IDF`). Token indices
are a stable 32-bit hash so a query and a document always agree on an index
without a stored vocabulary. Same recipe as fastembed's `Bm25`, minus stemming
and stopwords: an exact reference such as `DTU 20.1` must survive whole.
"""

import hashlib
import re
import unicodedata
from collections import Counter

from qdrant_client.models import PointStruct, SparseVector

K1 = 1.2
B = 0.75
AVG_DOC_LEN = 256

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.,\-/][a-z0-9]+)*")
_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae", "Œ": "oe", "Æ": "ae"})


def tokenize(text: str) -> list[str]:
    """Lowercase, fold accents, and split into tokens that keep references whole."""
    decomposed = unicodedata.normalize("NFD", text.translate(_LIGATURES))
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).lower()
    return _TOKEN_RE.findall(folded)


def _token_index(token: str) -> int:
    return int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big")


def _to_sparse(weights: dict[int, float]) -> SparseVector:
    indices = sorted(weights)
    return SparseVector(indices=indices, values=[weights[i] for i in indices])


def document_sparse_vector(text: str) -> SparseVector:
    """BM25 term-frequency weights for one chunk; colliding indices are summed."""
    tokens = tokenize(text)
    length = len(tokens)
    weights: dict[int, float] = {}
    for token, count in Counter(tokens).items():
        weight = count * (K1 + 1) / (count + K1 * (1 - B + B * length / AVG_DOC_LEN))
        index = _token_index(token)
        weights[index] = weights.get(index, 0.0) + weight
    return _to_sparse(weights)


def query_sparse_vector(text: str) -> SparseVector | None:
    """1.0 per distinct query token, or None when the query has no token."""
    indices = {_token_index(token) for token in tokenize(text)}
    if not indices:
        return None
    return _to_sparse({index: 1.0 for index in indices})


def to_hybrid_point(
    point_id: str | int, dense: list[float], payload: dict[str, object]
) -> PointStruct:
    """Build a `documents_v1` point: the dense vector reused as-is, sparse from `text`."""
    text = payload.get("text", "")
    return PointStruct(
        id=point_id,
        vector={
            "dense": dense,
            "sparse": document_sparse_vector(text if isinstance(text, str) else ""),
        },
        payload=payload,
    )
