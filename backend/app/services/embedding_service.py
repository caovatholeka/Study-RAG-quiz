# -*- coding: utf-8 -*-
"""
Dịch vụ tạo embedding vector và lưu trữ/tra cứu với ChromaDB.
Áp dụng Singleton pattern và Lazy Loading cho mô hình SentenceTransformer.
"""

import json
import logging
import os
import threading
from typing import Any, Dict, List, Optional, Union

try:
    import chromadb
    from chromadb.api.models.Collection import Collection
except ImportError:
    chromadb = None
    Collection = Any

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Dịch vụ tạo embeddings và tương tác với ChromaDB vector database.
    Singleton pattern đảm bảo chỉ có 1 instance trong suốt vòng đời ứng dụng.
    """

    _instance: Optional["EmbeddingService"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> "EmbeddingService":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        with self._lock:
            if getattr(self, "_initialized", False):
                return

            self.chroma_db_path: str = getattr(settings, "CHROMA_DB_PATH", "./chroma_db")
            self.embedding_model_name: str = getattr(
                settings, "EMBEDDING_MODEL", "intfloat/multilingual-e5-large"
            )

            # Lazy load attributes
            self._model = None
            self._model_lock = threading.Lock()

            # Khởi tạo ChromaDB Persistent Client
            os.makedirs(self.chroma_db_path, exist_ok=True)
            if chromadb is None:
                logger.error("Thư viện chromadb chưa được cài đặt.")
                raise RuntimeError("Thư viện chromadb chưa được cài đặt. Vui lòng cài đặt: pip install chromadb")

            try:
                self._chroma_client = chromadb.PersistentClient(path=self.chroma_db_path)
                logger.info(f"Khởi tạo ChromaDB PersistentClient tại {self.chroma_db_path}")
            except Exception as e:
                logger.error(f"Lỗi khi khởi tạo ChromaDB client tại {self.chroma_db_path}: {e}", exc_info=True)
                raise RuntimeError(f"Không thể kết nối ChromaDB: {e}") from e

            self._collection: Optional[Collection] = None
            self._initialized = True

    def _get_model(self):
        """
        Lazy load mô hình SentenceTransformer, đảm bảo chỉ load 1 lần duy nhất (thread-safe).

        Returns:
            SentenceTransformer: Instance mô hình embedding.

        Raises:
            RuntimeError: Nếu không thể tải mô hình.
        """
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    try:
                        logger.info(f"Bắt đầu tải mô hình embedding: {self.embedding_model_name}")
                        from sentence_transformers import SentenceTransformer

                        self._model = SentenceTransformer(self.embedding_model_name)
                        logger.info(f"Tải thành công mô hình embedding: {self.embedding_model_name}")
                    except Exception as e:
                        logger.error(
                            f"Lỗi nghiêm trọng khi tải mô hình embedding '{self.embedding_model_name}': {e}",
                            exc_info=True,
                        )
                        raise RuntimeError(
                            f"Không thể tải mô hình embedding '{self.embedding_model_name}': {e}"
                        ) from e
        return self._model

    def _get_collection(self) -> Collection:
        """
        Lấy hoặc tạo mới collection 'study_documents' với cosine similarity metric.

        Returns:
            chromadb.Collection: ChromaDB collection 'study_documents'.
        """
        if self._collection is None:
            try:
                self._collection = self._chroma_client.get_or_create_collection(
                    name="study_documents",
                    metadata={"hnsw:space": "cosine"},
                )
                logger.info("Đã kết nối collection 'study_documents' (metric: cosine)")
            except Exception as e:
                logger.error(f"Lỗi khi lấy/tạo collection 'study_documents': {e}", exc_info=True)
                raise RuntimeError(f"Không thể truy cập collection 'study_documents': {e}") from e
        return self._collection

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Tạo embeddings cho danh sách văn bản bằng local model.

        Args:
            texts: Danh sách các chuỗi văn bản cần embed.

        Returns:
            List[List[float]]: Danh sách các vector embedding.
        """
        if not texts:
            return []

        # Chuẩn hóa chuỗi văn bản (thay thế None, giữ text hợp lệ)
        cleaned_texts = [str(t) if t is not None else "" for t in texts]

        try:
            model = self._get_model()
            embeddings = model.encode(
                cleaned_texts,
                show_progress_bar=False,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Lỗi khi sinh embedding cho {len(texts)} văn bản: {e}", exc_info=True)
            raise RuntimeError(f"Lỗi sinh embedding: {e}") from e

    def embed_query(self, query: str) -> List[float]:
        """
        Tạo vector embedding cho 1 câu truy vấn.

        Args:
            query: Chuỗi văn bản truy vấn.

        Returns:
            List[float]: Vector embedding của truy vấn.
        """
        if not query or not query.strip():
            logger.warning("Truy vấn rỗng được truyền vào embed_query.")
            return []

        embeddings = self.embed_texts([query.strip()])
        return embeddings[0] if embeddings else []

    def _sanitize_metadata(self, metadata: Dict[str, Any], document_id: int) -> Dict[str, Union[str, int, float, bool]]:
        """
        Chuẩn hóa metadata để tương thích với quy định kiểu dữ liệu của ChromaDB
        (ChromaDB chỉ chấp nhận str, int, float, bool; không chấp nhận None hay list/dict lồng).

        Args:
            metadata: Metadata thô của chunk.
            document_id: ID của document sở hữu.

        Returns:
            Dict[str, Union[str, int, float, bool]]: Metadata đã được làm sạch.
        """
        sanitized: Dict[str, Union[str, int, float, bool]] = {
            "document_id": int(document_id),
            "chapter_id": int(metadata.get("chapter_id") or 0),
            "chapter_number": int(metadata.get("chapter_number") or 0),
            "chapter_title": str(metadata.get("chapter_title") or ""),
            "section": str(metadata.get("section") or ""),
            "page_start": int(metadata.get("page_start") or 0),
            "page_end": int(metadata.get("page_end") or 0),
        }

        # Xử lý topic_labels: nếu là list/dict thì serialize thành JSON string
        topic_labels = metadata.get("topic_labels")
        if isinstance(topic_labels, (list, dict)):
            sanitized["topic_labels"] = json.dumps(topic_labels, ensure_ascii=False)
        elif topic_labels is not None:
            sanitized["topic_labels"] = str(topic_labels)
        else:
            sanitized["topic_labels"] = ""

        # Sao chép thêm các thuộc tính nguyên thủy khác nếu có
        for k, v in metadata.items():
            if k not in sanitized:
                if v is None:
                    continue
                if isinstance(v, (str, int, float, bool)):
                    sanitized[k] = v
                elif isinstance(v, (list, dict)):
                    sanitized[k] = json.dumps(v, ensure_ascii=False)
                else:
                    sanitized[k] = str(v)

        return sanitized

    def add_chunks(self, document_id: int, chunks: List[Dict[str, Any]]) -> None:
        """
        Thêm hoặc cập nhật (upsert) các chunks của tài liệu vào ChromaDB.

        Mỗi chunk dict có cấu trúc:
            id (str): Định danh duy nhất của chunk
            text (str): Nội dung văn bản chunk
            metadata (dict): Thông tin đi kèm (document_id, chapter_id, chapter_number,
                             chapter_title, section, topic_labels, page_start, page_end)

        Args:
            document_id: ID của tài liệu sở hữu.
            chunks: Danh sách các dict chunk cần thêm.
        """
        if not chunks:
            logger.warning(f"Không có chunk nào để thêm vào ChromaDB cho document_id={document_id}.")
            return

        logger.info(f"Bắt đầu upsert {len(chunks)} chunks cho document ID {document_id} vào ChromaDB...")

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for idx, chunk in enumerate(chunks):
            chunk_id = chunk.get("id") or f"doc_{document_id}_chunk_{idx}"
            chunk_text = chunk.get("text", "")
            raw_meta = chunk.get("metadata", {})

            clean_meta = self._sanitize_metadata(raw_meta, document_id)

            ids.append(str(chunk_id))
            documents.append(chunk_text)
            metadatas.append(clean_meta)

        # Tạo embeddings cho toàn bộ danh sách chunks
        embeddings = self.embed_texts(documents)

        # Upsert vào ChromaDB collection
        collection = self._get_collection()
        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            logger.info(f"Upsert thành công {len(chunks)} chunks cho document ID {document_id}.")
        except Exception as e:
            logger.error(f"Lỗi khi upsert chunks vào ChromaDB cho document {document_id}: {e}", exc_info=True)
            raise RuntimeError(f"Lỗi khi upsert vào ChromaDB: {e}") from e

    def process_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Phương thức hỗ trợ tương thích với DocumentProcessor để upsert danh sách chunks.

        Args:
            chunks: Danh sách chunks cần upsert.
        """
        if not chunks:
            return

        # Nhóm theo document_id
        grouped: Dict[int, List[Dict[str, Any]]] = {}
        for chunk in chunks:
            doc_id = chunk.get("metadata", {}).get("document_id", 0)
            grouped.setdefault(doc_id, []).append(chunk)

        for doc_id, doc_chunks in grouped.items():
            self.add_chunks(doc_id, doc_chunks)

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Truy vấn vector DB bằng câu query text, trả về documents, metadatas, distances, ids.

        Args:
            query_text: Câu hỏi hoặc từ khóa tìm kiếm.
            n_results: Số lượng kết quả tối đa cần lấy.
            where: Bộ lọc metadata của ChromaDB (None nếu không lọc).

        Returns:
            Dict với keys: "documents", "metadatas", "distances", "ids".
        """
        empty_response = {"documents": [], "metadatas": [], "distances": [], "ids": []}

        if not query_text or not query_text.strip():
            logger.warning("query_text rỗng khi gọi query().")
            return empty_response

        collection = self._get_collection()

        try:
            total_items = collection.count()
        except Exception as e:
            logger.warning(f"Không thể lấy số lượng phần tử trong collection: {e}")
            total_items = 0

        if total_items == 0:
            logger.info("ChromaDB collection 'study_documents' hiện đang rỗng.")
            return empty_response

        limit = max(1, min(n_results, total_items))

        try:
            query_emb = self.embed_query(query_text)
            if not query_emb:
                return empty_response

            results = collection.query(
                query_embeddings=[query_emb],
                n_results=limit,
                where=where,
            )

            # ChromaDB trả về list of lists cho batch queries: [[...]]
            docs = results.get("documents", [[]])[0] if results.get("documents") else []
            metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
            dists = results.get("distances", [[]])[0] if results.get("distances") else []
            ids = results.get("ids", [[]])[0] if results.get("ids") else []

            return {
                "documents": docs,
                "metadatas": metas,
                "distances": dists,
                "ids": ids,
            }
        except Exception as e:
            logger.error(f"Lỗi khi thực hiện truy vấn ChromaDB: {e}", exc_info=True)
            return empty_response

    def query_by_chapter(
        self,
        query_text: str,
        chapter_number: int,
        document_id: int,
        n_results: int = 5,
    ) -> Dict[str, Any]:
        """
        Truy vấn vector DB trong phạm vi 1 chương cụ thể của 1 tài liệu.

        Args:
            query_text: Nội dung câu truy vấn.
            chapter_number: Số thứ tự chương cần lọc.
            document_id: ID của tài liệu.
            n_results: Số lượng kết quả cần lấy.

        Returns:
            Dict kết quả truy vấn {"documents", "metadatas", "distances", "ids"}.
        """
        where_filter = {
            "$and": [
                {"document_id": int(document_id)},
                {"chapter_number": int(chapter_number)},
            ]
        }
        return self.query(query_text=query_text, n_results=n_results, where=where_filter)

    def delete_document(self, document_id: int) -> None:
        """
        Xóa tất cả các chunks thuộc về một document trong ChromaDB.

        Args:
            document_id: ID của tài liệu cần xóa chunks.
        """
        collection = self._get_collection()
        try:
            total_before = collection.count()
            if total_before == 0:
                logger.info(f"Collection rỗng, không cần xóa cho document_id={document_id}.")
                return

            collection.delete(where={"document_id": int(document_id)})
            logger.info(f"Đã xóa toàn bộ vector chunks của document_id={document_id} khỏi ChromaDB.")
        except Exception as e:
            logger.warning(
                f"Lỗi hoặc không tìm thấy chunks khi xóa document_id={document_id} trong ChromaDB: {e}"
            )
