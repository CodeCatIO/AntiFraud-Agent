import hashlib
import json
import math
import os
import re
import tempfile
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


_REQUIRED_FIELDS = (
    "source_id",
    "document_id",
    "version",
    "title",
    "source_title",
    "publisher",
    "source_url",
    "published_at",
    "retrieved_at",
    "locator",
    "license_status",
    "content",
    "retrieval_keywords",
)
_TOKENIZER_VERSION = "unicode-word-and-cjk-ngrams-2-3-v1"
_INDEX_SCHEMA_VERSION = 2
_DEFAULT_ROOT = Path(__file__).resolve().parents[1]


def _source_path() -> Path:
    return Path(os.getenv("KNOWLEDGE_SOURCE_PATH", _DEFAULT_ROOT / "data" / "knowledge_sources.jsonl"))


def _index_dir() -> Path:
    return Path(os.getenv("KNOWLEDGE_INDEX_DIR", _DEFAULT_ROOT / "data" / "indexes"))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _read_sources(source_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    with source_path.open("r", encoding="utf-8") as source_file:
        for line_number, line in enumerate(source_file, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on source line {line_number}") from exc
            if not isinstance(row, dict) or any(field not in row for field in _REQUIRED_FIELDS):
                raise ValueError(f"Source line {line_number} is missing required metadata")
            if any(not row[field] for field in _REQUIRED_FIELDS if field != "retrieval_keywords"):
                raise ValueError(f"Source line {line_number} has empty required metadata")
            if not isinstance(row["retrieval_keywords"], list) or not all(
                isinstance(keyword, str) and keyword.strip()
                for keyword in row["retrieval_keywords"]
            ):
                raise ValueError(f"Source line {line_number} has invalid retrieval_keywords")
            if not row["source_url"].startswith("https://"):
                raise ValueError(f"Source line {line_number} must use an HTTPS source URL")
            document_id = str(row["document_id"])
            if document_id in seen:
                raise ValueError(f"Duplicate document_id: {document_id}")
            seen.add(document_id)
            rows.append(row)
    if not rows:
        raise ValueError("Knowledge source file contains no source cards")
    return sorted(rows, key=lambda row: str(row["document_id"]))


def _make_chunk(row: dict[str, Any]) -> dict[str, Any]:
    chunk_text = str(row["content"]).strip()
    if not chunk_text:
        raise ValueError(f"Source {row['document_id']} has no content")
    identity = "|".join(
        (
            str(row["source_id"]),
            str(row["document_id"]),
            str(row["version"]),
            str(row["locator"]),
            chunk_text,
        )
    )
    chunk_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    searchable_text = " ".join(
        (str(row["title"]), chunk_text, " ".join(row["retrieval_keywords"]))
    )
    return {
        "chunk_id": chunk_id,
        "document_id": row["document_id"],
        "source_id": row["source_id"],
        "version": row["version"],
        "title": row["title"],
        "source_title": row["source_title"],
        "publisher": row["publisher"],
        "source_url": row["source_url"],
        "published_at": row["published_at"],
        "retrieved_at": row["retrieved_at"],
        "locator": row["locator"],
        "license_status": row["license_status"],
        "content_type": "paraphrase",
        "text": chunk_text,
        "searchable_text": searchable_text,
    }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary_file:
        temporary_file.write(content)
        temporary_path = Path(temporary_file.name)
    os.replace(temporary_path, path)


def _write_pointer(path: Path, index_version: str | None) -> None:
    if index_version is None:
        path.unlink(missing_ok=True)
        return
    _atomic_write(path, _canonical_json({"index_version": index_version}) + "\n")


def build_index(
    source_path: Path | None = None,
    index_dir: Path | None = None,
) -> dict[str, Any]:
    sources_path = source_path or _source_path()
    indexes_path = index_dir or _index_dir()
    rows = _read_sources(sources_path)
    chunks = [_make_chunk(row) for row in rows]
    version_input = {
        "schema_version": _INDEX_SCHEMA_VERSION,
        "tokenizer": _TOKENIZER_VERSION,
        "sources": rows,
    }
    index_version = hashlib.sha256(_canonical_json(version_input).encode("utf-8")).hexdigest()[:16]
    index_data = {
        "manifest": {
            "schema_version": _INDEX_SCHEMA_VERSION,
            "index_version": index_version,
            "source_count": len(rows),
            "chunk_count": len(chunks),
            "tokenizer": _TOKENIZER_VERSION,
        },
        "chunks": chunks,
    }
    index_file = indexes_path / f"index-{index_version}.json"
    index_content = _canonical_json(index_data) + "\n"
    if not index_file.exists():
        _atomic_write(index_file, index_content)
    elif index_file.read_text(encoding="utf-8") != index_content:
        raise ValueError(f"Existing immutable index file differs: {index_file.name}")

    current_pointer = indexes_path / "current.json"
    previous_pointer = indexes_path / "previous.json"
    old_version = _read_pointer(current_pointer, indexes_path, missing_ok=True)
    if old_version != index_version:
        if old_version is not None:
            _write_pointer(previous_pointer, old_version)
        _write_pointer(current_pointer, index_version)
    elif not current_pointer.exists():
        _write_pointer(current_pointer, index_version)
    return index_data["manifest"]


def _read_pointer(pointer_path: Path, index_dir: Path, missing_ok: bool = False) -> str | None:
    if not pointer_path.exists():
        if missing_ok:
            return None
        raise FileNotFoundError("Knowledge index pointer is not configured")
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    index_version = pointer.get("index_version") if isinstance(pointer, dict) else None
    if not isinstance(index_version, str) or not re.fullmatch(r"[0-9a-f]{16}", index_version):
        raise ValueError("Knowledge index pointer is invalid")
    if not (index_dir / f"index-{index_version}.json").is_file():
        raise ValueError("Knowledge index snapshot is missing")
    return index_version


def rollback_index(index_dir: Path | None = None) -> dict[str, str]:
    indexes_path = index_dir or _index_dir()
    current_pointer = indexes_path / "current.json"
    previous_pointer = indexes_path / "previous.json"
    current_version = _read_pointer(current_pointer, indexes_path)
    previous_version = _read_pointer(previous_pointer, indexes_path)
    _write_pointer(current_pointer, previous_version)
    _write_pointer(previous_pointer, current_version)
    return {"current": previous_version, "previous": current_version}


@lru_cache(maxsize=8)
def _load_snapshot(index_dir: str, index_version: str) -> dict[str, Any]:
    return json.loads(
        (Path(index_dir) / f"index-{index_version}.json").read_text(encoding="utf-8")
    )


def _load_current_index(index_dir: Path | None = None) -> dict[str, Any]:
    indexes_path = (index_dir or _index_dir()).resolve()
    index_version = _read_pointer(indexes_path / "current.json", indexes_path)
    assert index_version is not None
    return _load_snapshot(str(indexes_path), index_version)


@lru_cache(maxsize=16384)
def _tokens(text: str) -> list[str]:
    terms: list[str] = []
    for match in re.finditer(r"[a-z0-9]+|[\u3400-\u9fff]+", text.casefold()):
        segment = match.group(0)
        if "\u3400" <= segment[0] <= "\u9fff":
            if len(segment) == 1:
                terms.append(segment)
            else:
                terms.extend(segment[index : index + 2] for index in range(len(segment) - 1))
                terms.extend(segment[index : index + 3] for index in range(len(segment) - 2))
        else:
            terms.append(segment)
    return terms


def _rank_bm25(query: str, chunks: list[dict[str, Any]]) -> list[tuple[int, float]]:
    query_terms = set(_tokens(query))
    tokenized = [_tokens(chunk["searchable_text"]) for chunk in chunks]
    document_frequency = Counter(term for terms in tokenized for term in set(terms))
    average_length = sum(map(len, tokenized)) / max(1, len(tokenized))
    count = len(chunks)
    scored: list[tuple[int, float]] = []
    for position, terms in enumerate(tokenized):
        frequencies = Counter(terms)
        score = 0.0
        for term in query_terms:
            frequency = frequencies[term]
            if not frequency:
                continue
            inverse_frequency = math.log(
                1 + (count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5)
            )
            denominator = frequency + 1.5 * (1 - 0.75 + 0.75 * len(terms) / max(1.0, average_length))
            score += inverse_frequency * frequency * 2.5 / denominator
        if score > 0:
            scored.append((position, score))
    return sorted(scored, key=lambda item: (-item[1], chunks[item[0]]["chunk_id"]))


def _rank_tfidf(query: str, chunks: list[dict[str, Any]]) -> list[tuple[int, float]]:
    query_terms = Counter(_tokens(query))
    tokenized = [_tokens(chunk["searchable_text"]) for chunk in chunks]
    document_frequency = Counter(term for terms in tokenized for term in set(terms))
    count = len(chunks)

    def weighted_vector(frequencies: Counter[str]) -> dict[str, float]:
        vector: dict[str, float] = {}
        for term, frequency in frequencies.items():
            inverse_frequency = math.log((count + 1) / (document_frequency[term] + 1)) + 1
            vector[term] = (1 + math.log(frequency)) * inverse_frequency
        return vector

    query_vector = weighted_vector(query_terms)
    query_norm = math.sqrt(sum(weight * weight for weight in query_vector.values()))
    scored: list[tuple[int, float]] = []
    for position, terms in enumerate(tokenized):
        document_vector = weighted_vector(Counter(terms))
        document_norm = math.sqrt(sum(weight * weight for weight in document_vector.values()))
        if not query_norm or not document_norm:
            continue
        dot_product = sum(
            query_weight * document_vector.get(term, 0.0)
            for term, query_weight in query_vector.items()
        )
        score = dot_product / (query_norm * document_norm)
        if score > 0:
            scored.append((position, score))
    return sorted(scored, key=lambda item: (-item[1], chunks[item[0]]["chunk_id"]))


def _rank_hybrid(
    bm25_ranking: list[tuple[int, float]],
    tfidf_ranking: list[tuple[int, float]],
    reciprocal_rank_constant: int = 60,
) -> list[tuple[int, float]]:
    fused_scores: dict[int, float] = {}
    for ranking in (bm25_ranking, tfidf_ranking):
        for rank, (position, _score) in enumerate(ranking, start=1):
            fused_scores[position] = fused_scores.get(position, 0.0) + 1 / (
                reciprocal_rank_constant + rank
            )
    return sorted(fused_scores.items(), key=lambda item: (-item[1], item[0]))


def search_knowledge(
    query: str,
    top_k: int = 5,
    strategy: str = "hybrid",
    index_dir: Path | None = None,
) -> dict[str, Any]:
    if not 1 <= top_k <= 10:
        raise ValueError("top_k must be between 1 and 10")
    if strategy not in {"bm25", "tfidf", "hybrid"}:
        raise ValueError("strategy must be bm25, tfidf, or hybrid")
    index_data = _load_current_index(index_dir)
    chunks = index_data["chunks"]
    bm25_ranking = _rank_bm25(query, chunks)
    tfidf_ranking = _rank_tfidf(query, chunks)
    ranking = {
        "bm25": bm25_ranking,
        "tfidf": tfidf_ranking,
        "hybrid": _rank_hybrid(bm25_ranking, tfidf_ranking),
    }[strategy]
    results = []
    for rank, (position, score) in enumerate(ranking[:top_k], start=1):
        chunk = chunks[position]
        methods = []
        for method, method_ranking in (("bm25", bm25_ranking), ("tfidf", tfidf_ranking)):
            method_rank = next(
                (index for index, (candidate, _score) in enumerate(method_ranking, start=1)
                 if candidate == position),
                None,
            )
            if method_rank is not None:
                methods.append({"method": method, "rank": method_rank})
        results.append(
            {
                "chunkId": chunk["chunk_id"],
                "documentId": chunk["document_id"],
                "sourceId": chunk["source_id"],
                "version": chunk["version"],
                "title": chunk["title"],
                "sourceTitle": chunk["source_title"],
                "publisher": chunk["publisher"],
                "sourceUrl": chunk["source_url"],
                "publishedAt": chunk["published_at"],
                "retrievedAt": chunk["retrieved_at"],
                "locator": chunk["locator"],
                "licenseStatus": chunk["license_status"],
                "excerpt": chunk["text"],
                "excerptType": chunk["content_type"],
                "score": round(score, 8),
                "rank": rank,
                "retrievalMethods": methods,
            }
        )
    return {
        "status": "completed",
        "query": query,
        "strategy": strategy,
        "indexVersion": index_data["manifest"]["index_version"],
        "results": results,
        "message": None if results else "No supporting source matched this query.",
    }
