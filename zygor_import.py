import argparse
import os
import re
from pathlib import Path
from typing import List, Dict


GUIDE_PATTERNS = [
    # ZygorGuidesViewer:RegisterGuide("Title", [[ body ]])
    re.compile(r"ZygorGuidesViewer\s*:\s*RegisterGuide\s*\(\s*([\"\'])\s*(?P<title>.*?)\1\s*,\s*\[\[(?P<body>.*?)\]\]", re.S),
    # ZGV:RegisterGuide("Title", [[ body ]])
    re.compile(r"ZGV\s*:\s*RegisterGuide\s*\(\s*([\"\'])\s*(?P<title>.*?)\1\s*,\s*\[\[(?P<body>.*?)\]\]", re.S),
    # ZygorGuidesViewer:RegisterGuide("Title", { ... }, [[ body ]])
    re.compile(r"ZygorGuidesViewer\s*:\s*RegisterGuide\s*\(\s*([\"\'])\s*(?P<title>.*?)\1\s*,\s*\{.*?\},\s*\[\[(?P<body>.*?)\]\]", re.S),
    # ZGV:RegisterGuide("Title", { ... }, [[ body ]])
    re.compile(r"ZGV\s*:\s*RegisterGuide\s*\(\s*([\"\'])\s*(?P<title>.*?)\1\s*,\s*\{.*?\},\s*\[\[(?P<body>.*?)\]\]", re.S),
]


def extract_guides(lua_text: str):
    guides = []
    for pat in GUIDE_PATTERNS:
        for m in pat.finditer(lua_text):
            title = (m.group("title") or "Untitled").strip()
            body = (m.group("body") or "").strip()
            if body:
                guides.append({"title": title, "body": body})
    return guides


def sanitize_filename(name: str) -> str:
    keep = [c if c.isalnum() or c in (" ", "-", "_", ".") else "_" for c in name]
    cleaned = "".join(keep).strip().replace(" ", "_")
    return cleaned or "guide"


def chunk_text(s: str, limit: int = 800):
    s = s.strip()
    out = []
    while s:
        if len(s) <= limit:
            out.append(s)
            break
        cut = s.rfind("\n", 0, limit)
        if cut == -1 or cut < int(limit * 0.6):
            cut = limit
        out.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    return out


def write_markdown(out_dir: Path, title: str, body: str, tag: str = "zygor", chunk: int = 800):
    base = sanitize_filename(title)
    parts = chunk_text(body, chunk)
    for idx, content in enumerate(parts, 1):
        fname = f"{base}_{idx:03d}.md" if len(parts) > 1 else f"{base}.md"
        path = out_dir / fname
        header = f"# {title}\n\nSource: {tag}\n\n"
        path.write_text(header + content + "\n", encoding="utf-8")


def append_kb_entries(entries: List[Dict], title: str, body: str, tag: str = "Zygor", chunk: int = 800):
    base_id = sanitize_filename(title).lower()
    parts = chunk_text(body, chunk)
    for idx, content in enumerate(parts, 1):
        eid = f"{base_id}_{idx:03d}" if len(parts) > 1 else base_id
        entries.append({
            "id": eid,
            "title": title,
            "tags": [tag],
            "text": content,
        })


def process_dir_md(src_dir: Path, out_dir: Path, tag: str = "zygor", chunk: int = 800):
    count = 0
    for root, _, files in os.walk(src_dir):
        for name in files:
            if not name.lower().endswith(".lua"):
                continue
            p = Path(root) / name
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            guides = extract_guides(text)
            for g in guides:
                write_markdown(out_dir, g["title"], g["body"], tag=tag, chunk=chunk)
                count += 1
    return count


def process_dir_kb(src_dir: Path, kb_out: Path, tag: str = "Zygor", chunk: int = 800):
    import yaml  # type: ignore
    entries: List[Dict] = []
    count = 0
    for root, _, files in os.walk(src_dir):
        for name in files:
            if not name.lower().endswith(".lua"):
                continue
            p = Path(root) / name
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            guides = extract_guides(text)
            for g in guides:
                append_kb_entries(entries, g["title"], g["body"], tag=tag, chunk=chunk)
                count += 1
    data = {"entries": entries}
    kb_out.parent.mkdir(parents=True, exist_ok=True)
    kb_out.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return count, len(entries)


def main():
    ap = argparse.ArgumentParser(description="Import Zygor Lua guides for RAG.")
    ap.add_argument("--src", required=True, help="Path to Zygor addon folder (contains .lua guides)")
    ap.add_argument("--mode", choices=["md", "md-single", "kb"], default="md", help="md: chunked markdown files; md-single: one markdown per guide; kb: single KB YAML file")
    ap.add_argument("--out", default="docs/zygor", help="Output folder (md, md-single) or KB YAML path (kb)")
    ap.add_argument("--tag", default="Zygor", help="Tag/source label to include")
    ap.add_argument("--chunk", type=int, default=800, help="Chunk size in characters")
    args = ap.parse_args()

    src = Path(args.src)
    if args.mode == "md":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        count = process_dir_md(src, out, tag=args.tag, chunk=args.chunk)
        print(f"Imported {count} guides into {out}")
    elif args.mode == "md-single":
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        # Reuse extractor, but write single file per guide (no chunk files)
        count = 0
        for root, _, files in os.walk(src):
            for name in files:
                if not name.lower().endswith(".lua"):
                    continue
                p = Path(root) / name
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                guides = extract_guides(text)
                for g in guides:
                    base = sanitize_filename(g["title"]) or "guide"
                    path = out / f"{base}.md"
                    header = f"# {g['title']}\n\nSource: {args.tag}\n\n"
                    path.write_text(header + g["body"].strip() + "\n", encoding="utf-8")
                    count += 1
        print(f"Imported {count} guides (one file each) into {out}")
    else:
        kb_out = Path(args.out)
        count, passages = process_dir_kb(src, kb_out, tag=args.tag, chunk=args.chunk)
        print(f"Imported {count} guides, wrote {passages} KB entries to {kb_out}")


if __name__ == "__main__":
    main()
