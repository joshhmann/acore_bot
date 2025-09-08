import os
import re
from typing import List, Dict, Any, Optional


def _chunk_text(s: str, limit: int = 800) -> List[str]:
    s = (s or "").strip()
    if not s:
        return []
    out: List[str] = []
    while s:
        if len(s) <= limit:
            out.append(s)
            break
        cut = s.rfind("\n", 0, limit)
        if cut == -1 or cut < int(limit * 0.6):
            cut = limit
        chunk, s = s[:cut].rstrip(), s[cut:].lstrip()
        out.append(chunk)
    return out


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _read_pdf_text(path: str) -> str:
    try:
        import PyPDF2  # type: ignore
    except Exception:
        return ""
    try:
        text_parts: List[str] = []
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    continue
        return "\n".join([t for t in text_parts if t])
    except Exception:
        return ""


def _load_yaml(path: str) -> Any:
    try:
        import yaml  # type: ignore
    except Exception:
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


class RagStore:
    def __init__(self, kb_path: Optional[str], docs_dir: Optional[str]):
        self.kb_path = kb_path or ""
        self.docs_dir = docs_dir or ""
        self.kb: List[Dict[str, Any]] = []
        self.docs: List[Dict[str, Any]] = []

    def load_all(self) -> None:
        self.load_kb()
        self.load_docs()

    def load_kb(self) -> None:
        path = self.kb_path
        self.kb = []
        if not path:
            return
        lower = path.lower()
        entries: List[Dict[str, Any]] = []
        data = None
        if lower.endswith(".yaml") or lower.endswith(".yml"):
            data = _load_yaml(path)
        else:
            import json
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
            except Exception:
                data = None
        if isinstance(data, list):
            src = data
        elif isinstance(data, dict):
            src = data.get("entries") or []
        else:
            src = []
        for e in src:
            if not isinstance(e, dict):
                continue
            _id = str(e.get("id") or "").strip()
            title = str(e.get("title") or "").strip()
            text = str(e.get("text") or "").strip()
            tags = e.get("tags") or []
            if not _id or not title or not text:
                continue
            if not isinstance(tags, list):
                tags = []
            entries.append({"id": _id, "title": title, "text": text, "tags": [str(t) for t in tags]})
        self.kb = entries

    def load_docs(self) -> None:
        root = self.docs_dir
        self.docs = []
        if not root or not os.path.isdir(root):
            return
        out: List[Dict[str, Any]] = []
        for r, _, files in os.walk(root):
            for name in files:
                path = os.path.join(r, name)
                lower = name.lower()
                title = name
                text = ""
                if lower.endswith(".md") or lower.endswith(".txt"):
                    try:
                        text = _read_text_file(path)
                    except Exception:
                        continue
                elif lower.endswith(".pdf"):
                    text = _read_pdf_text(path)
                elif lower.endswith(".yaml") or lower.endswith(".yml"):
                    data = _load_yaml(path)
                    if isinstance(data, dict):
                        # Support {title, text} or {title, sections: [ ... ]}
                        title = str(data.get("title") or title)
                        if isinstance(data.get("sections"), list):
                            text = "\n\n".join([str(x) for x in data.get("sections") if x])
                        elif data.get("text"):
                            text = str(data.get("text"))
                else:
                    continue
                if not text:
                    continue
                chunks = _chunk_text(text, 800)
                for i, ch in enumerate(chunks, 1):
                    out.append({
                        "id": f"{path}#{i}",
                        "title": title,
                        "text": ch,
                        "tags": ["docs"],
                    })
        self.docs = out

    def search_kb(self, query: str, limit: int = 3, return_scores: bool = False):
        q = (query or "").lower().strip()
        if not q:
            return []
        tokens = [t for t in re.split(r"\W+", q) if t]
        scored: List[tuple[int, Dict[str, Any]]] = []
        for e in self.kb:
            title = e.get("title", "")
            text = e.get("text", "")
            tags = e.get("tags", [])
            hay_title = title.lower()
            hay_text = text.lower()
            hay_tags = " ".join([str(t).lower() for t in tags])
            score = 0
            if q and (q in hay_title):
                score += 10
            if q and (q in hay_text):
                score += 5
            if q and (q in hay_tags):
                score += 6
            for t in tokens:
                if t in hay_title:
                    score += 4
                if t in hay_tags:
                    score += 3
                if t in hay_text:
                    score += 1
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max(1, limit)]
        if return_scores:
            return top
        return [e for _, e in top]

    def search_docs(self, query: str, limit: int = 2, return_scores: bool = False):
        q = (query or "").lower().strip()
        if not q:
            return []
        tokens = [t for t in re.split(r"\W+", q) if t]
        scored: List[tuple[int, Dict[str, Any]]] = []
        for e in self.docs:
            title = e.get("title", "")
            text = e.get("text", "")
            hay_title = title.lower()
            hay_text = text.lower()
            score = 0
            if q and (q in hay_title):
                score += 8
            if q and (q in hay_text):
                score += 5
            for t in tokens:
                if t in hay_title:
                    score += 3
                if t in hay_text:
                    score += 1
            if score > 0:
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:max(1, limit)]
        if return_scores:
            return top
        return [e for _, e in top]
