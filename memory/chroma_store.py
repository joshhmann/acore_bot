from __future__ import annotations

from typing import Any

from .base import MemoryNamespace, MemoryStore

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None  # type: ignore
    Settings = None  # type: ignore


class ChromaStore(MemoryStore):
    """MemoryStore implementation using ChromaDB embedded with duckdb+parquet backend.

    Each namespace (persona_id:room_id) is stored as a separate ChromaDB collection.
    """

    def __init__(self, persist_directory: str = "data/chroma_db") -> None:
        if not CHROMADB_AVAILABLE:
            raise ImportError(
                "ChromaDB is required for ChromaStore. "
                "Install with: pip install chromadb"
            )

        self.settings = Settings(
            anonymized_telemetry=False,
            persist_directory=persist_directory,
        )
        self.client = chromadb.Client(self.settings)
        self._persist_directory = persist_directory

    def _collection_name(self, namespace: MemoryNamespace) -> str:
        """Generate a valid ChromaDB collection name from namespace.

        ChromaDB collection names must be 3-63 characters, alphanumeric,
        hyphens, underscores, or periods.
        """
        safe_persona = namespace.persona_id.replace("/", "_").replace(":", "_")
        safe_room = namespace.room_id.replace("/", "_").replace(":", "_")
        name = f"{safe_persona}_{safe_room}"
        # Ensure valid length (3-63 chars)
        if len(name) < 3:
            name = name + "_ns"
        if len(name) > 63:
            name = name[:63]
        return name

    def _get_or_create_collection(self, namespace: MemoryNamespace) -> Any:
        """Get or create a ChromaDB collection for the given namespace."""
        name = self._collection_name(namespace)
        return self.client.get_or_create_collection(
            name=name,
            metadata={"namespace": namespace.key()},
        )

    async def append_short_term(
        self, namespace: MemoryNamespace, message: dict[str, Any]
    ) -> None:
        """Append a message to short-term memory for the namespace."""
        collection = self._get_or_create_collection(namespace)

        # Generate a unique ID based on timestamp and content hash if available
        msg_id = (
            message.get("id") or message.get("timestamp") or str(hash(str(message)))
        )
        doc_id = f"st_{msg_id}"

        # Store the message as a document
        collection.upsert(
            ids=[doc_id],
            documents=[str(message)],
            metadatas=[
                {"type": "short_term", "timestamp": message.get("timestamp", "")}
            ],
        )

        # Keep only last 100 short-term messages per namespace
        results = collection.get(
            where={"type": "short_term"},
            include=["metadatas"],
        )

        if results and results["ids"]:
            ids = results["ids"]
            if len(ids) > 100:
                # Sort by timestamp if available, otherwise by ID order
                metadatas = results.get("metadatas") or [{} for _ in ids]
                sorted_items = sorted(
                    zip(ids, metadatas),
                    key=lambda x: x[1].get("timestamp", x[0]),
                )
                # Delete oldest entries (first in sorted list)
                to_delete = [item[0] for item in sorted_items[:-100]]
                collection.delete(ids=to_delete)

    async def get_short_term(
        self,
        namespace: MemoryNamespace,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Get recent short-term messages for the namespace."""
        collection = self._get_or_create_collection(namespace)

        results = collection.get(
            where={"type": "short_term"},
            include=["documents", "metadatas"],
        )

        if not results or not results["ids"]:
            return []

        ids = results["ids"]
        documents = results.get("documents") or []
        metadatas = results.get("metadatas") or [{} for _ in ids]

        # Sort by timestamp if available
        sorted_items = sorted(
            zip(ids, documents, metadatas),
            key=lambda x: x[2].get("timestamp", x[0]),
        )

        # Return last 'limit' items
        selected = sorted_items[-max(1, limit) :]

        # Parse the stored string representation back to dict
        import ast

        messages = []
        for _, doc, _ in selected:
            try:
                msg = ast.literal_eval(doc)
                if isinstance(msg, dict):
                    messages.append(msg)
            except (ValueError, SyntaxError):
                # If parsing fails, treat as raw content
                messages.append({"content": doc})

        return messages

    async def get_long_term_summary(self, namespace: MemoryNamespace) -> str:
        """Get the long-term summary for the namespace."""
        collection = self._get_or_create_collection(namespace)

        try:
            result = collection.get(
                ids=["long_term_summary"],
                include=["documents"],
            )
            if result and result["documents"]:
                return str(result["documents"][0])
        except Exception:
            pass

        return ""

    async def set_long_term_summary(
        self, namespace: MemoryNamespace, summary: str
    ) -> None:
        """Set the long-term summary for the namespace."""
        collection = self._get_or_create_collection(namespace)

        collection.upsert(
            ids=["long_term_summary"],
            documents=[summary],
            metadatas=[{"type": "long_term_summary"}],
        )

    async def get_state(self, namespace: MemoryNamespace) -> dict[str, Any]:
        """Get the state for the namespace."""
        collection = self._get_or_create_collection(namespace)

        try:
            result = collection.get(
                ids=["state"],
                include=["documents"],
            )
            if result and result["documents"]:
                import json

                state_str = result["documents"][0]
                return json.loads(state_str)
        except Exception:
            pass

        return {}

    async def set_state(
        self, namespace: MemoryNamespace, state: dict[str, Any]
    ) -> None:
        """Set the state for the namespace."""
        collection = self._get_or_create_collection(namespace)
        import json

        collection.upsert(
            ids=["state"],
            documents=[json.dumps(state)],
            metadatas=[{"type": "state"}],
        )

    async def delete(self, namespace: MemoryNamespace) -> None:
        """Delete all data for a namespace (collection)."""
        name = self._collection_name(namespace)
        try:
            self.client.delete_collection(name)
        except Exception:
            # Collection may not exist
            pass

    async def list_namespaces(self) -> list[MemoryNamespace]:
        """List all namespaces (collections) in the store."""
        namespaces = []

        try:
            collections = self.client.list_collections()
            for collection in collections:
                metadata = collection.metadata or {}
                namespace_key = metadata.get("namespace")
                if namespace_key and ":" in namespace_key:
                    persona_id, room_id = namespace_key.split(":", 1)
                    namespaces.append(
                        MemoryNamespace(
                            persona_id=persona_id,
                            room_id=room_id,
                        )
                    )
        except Exception:
            pass

        return namespaces

    async def clear_namespace(self, namespace: MemoryNamespace) -> None:
        """Clear all data within a namespace but keep the collection."""
        collection = self._get_or_create_collection(namespace)

        try:
            # Get all IDs and delete them
            results = collection.get(include=[])
            if results and results["ids"]:
                collection.delete(ids=results["ids"])
        except Exception:
            pass
