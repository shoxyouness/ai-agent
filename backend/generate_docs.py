
import os
import fnmatch
import hashlib
from pathlib import Path
from typing import Dict, List, Tuple

from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------
# CONFIG
# ---------------------------

DEFAULT_IGNORE_DIRS = {
    ".venv", "venv", "env","tests",
    ".git", ".github",
    "__pycache__",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
    "node_modules",
    "dist", "build", ".next", "out",
    ".idea", ".vscode",
    "chroma_db", "chromadb", "vectorstore", "qdrant",
    "logs", "tmp", ".cache",
    ".terraform",
    "coverage", "htmlcov",
}

DEFAULT_IGNORE_FILES = {
    ".env", ".env.local", ".env.dev", ".env.prod",
    "poetry.lock", "package-lock.json", "yarn.lock",
}

DEFAULT_IGNORE_PATTERNS = [
    "*.pem", "*.key", "*.crt",
    "*.sqlite", "*.db",
    "*.log",
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp",
    "*.pdf", "*.zip", "*.tar", "*.gz", "*.7z",
    "*.mp4", "*.mov", "*.avi",
]

INCLUDE_EXTENSIONS = {
    ".py", ".ts", ".tsx", ".js", ".jsx",
    ".json", ".yaml", ".yml",
    ".toml", ".ini", ".cfg",
    ".md", ".txt",
    ".dockerfile", "dockerfile",
    ".env.example",
}

MAX_FILE_CHARS = 35_000   # hard guard for extremely large files
CHUNK_TARGET_CHARS = 80_000  # how big each LLM request chunk can be
MODEL = "gpt-4.1-mini"  # good for documentation (cheap + smart)


SYSTEM_PROMPT = """
Du bist ein Senior Software Architect und Tech Writer.

Deine Aufgabe:
- Erstelle eine professionelle, gut strukturierte Dokumentation (Markdown) für das gesamte Codebase.
- Schreibe so, dass ein neuer Entwickler das Projekt schnell versteht.
- Wenn möglich: erkläre Architektur, Module, Datenfluss, und wichtige Klassen/Funktionen.
- Dokumentiere auch Entry Points, APIs (FastAPI), Background Jobs, Docker, Konfiguration.
- Erstelle klare Überschriften, Bullet Points, Beispiele.
- Sei exakt und codebezogen (nicht raten).

Output:
- Gib ausschließlich Markdown zurück.
"""


# ---------------------------
# HELPERS
# ---------------------------

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def should_ignore_dir(dir_name: str) -> bool:
    return dir_name in DEFAULT_IGNORE_DIRS


def should_ignore_file(file_path: Path) -> bool:
    name = file_path.name

    if name in DEFAULT_IGNORE_FILES:
        return True

    for pat in DEFAULT_IGNORE_PATTERNS:
        if fnmatch.fnmatch(name.lower(), pat.lower()):
            return True

    return False


def is_included_file(file_path: Path) -> bool:
    # allow exact filename matches like "Dockerfile"
    if file_path.name.lower() == "dockerfile":
        return True

    ext = file_path.suffix.lower()
    return ext in INCLUDE_EXTENSIONS or file_path.name.endswith(".env.example")


def safe_read_text(file_path: Path) -> str:
    try:
        data = file_path.read_text(encoding="utf-8", errors="ignore")
        if len(data) > MAX_FILE_CHARS:
            # truncate large files
            data = data[:MAX_FILE_CHARS] + "\n\n# [TRUNCATED: file was too large]\n"
        return data
    except Exception as e:
        return f"# [ERROR reading file {file_path}: {e}]"


def collect_project_files(root: Path) -> List[Path]:
    collected: List[Path] = []

    for current_root, dirs, files in os.walk(root):
        current_root_path = Path(current_root)

        # mutate dirs in-place to skip
        dirs[:] = [d for d in dirs if not should_ignore_dir(d)]

        for f in files:
            fp = current_root_path / f
            if should_ignore_file(fp):
                continue
            if not is_included_file(fp):
                continue
            collected.append(fp)

    collected.sort()
    return collected


def build_project_tree(files: List[Path], root: Path) -> str:
    """
    Simple project tree for context.
    """
    tree = {}
    for fp in files:
        rel = fp.relative_to(root).parts
        cur = tree
        for part in rel[:-1]:
            cur = cur.setdefault(part, {})
        cur.setdefault("__files__", []).append(rel[-1])

    def render(node: dict, indent: int = 0) -> str:
        out = []
        for k in sorted([x for x in node.keys() if x != "__files__"]):
            out.append("  " * indent + f"- {k}/")
            out.append(render(node[k], indent + 1))
        for f in sorted(node.get("__files__", [])):
            out.append("  " * indent + f"- {f}")
        return "\n".join([x for x in out if x.strip()])

    return render(tree).strip()


def chunk_files(file_contents: List[Tuple[str, str]]) -> List[str]:
    """
    file_contents: list of (relative_path, content)
    Returns: list of chunk strings
    """
    chunks: List[str] = []
    cur = []
    cur_len = 0

    for rel_path, content in file_contents:
        block = f"\n\n# FILE: {rel_path}\n```text\n{content}\n```\n"
        if cur_len + len(block) > CHUNK_TARGET_CHARS and cur:
            chunks.append("".join(cur))
            cur = []
            cur_len = 0
        cur.append(block)
        cur_len += len(block)

    if cur:
        chunks.append("".join(cur))

    return chunks


def call_openai_for_docs(client: OpenAI, project_name: str, project_tree: str, chunk_text: str, chunk_index: int, chunk_count: int) -> str:
    user_prompt = f"""
Projektname: {project_name}

Projekt-Struktur (Tree):
{project_tree}

Du erhältst nun einen Teil des Codes (Chunk {chunk_index}/{chunk_count}).
Erstelle aus diesem Teil eine Doku (Markdown), aber so, dass sie später in eine Gesamtdoku integriert werden kann.

Wichtig:
- keine Fantasie, nur was im Code wirklich steht
- erwähne relevante Module, Klassen, Tools, Endpoints, Flows
- liste wichtige Funktionen + Zweck
- wenn du FastAPI siehst: endpoints + payloads beschreiben
- wenn du LangGraph / LangChain siehst: graph nodes / edges / state beschreiben

CODE-CHUNK:
{chunk_text}
""".strip()

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


def call_openai_merge(client: OpenAI, partial_docs: List[str], project_name: str, project_tree: str) -> str:
    merged_input = "\n\n---\n\n".join(
        [f"# PART {i+1}\n{doc}" for i, doc in enumerate(partial_docs)]
    )

    user_prompt = f"""
Du bekommst mehrere Dokumentations-Teile (PART 1..N) für das Projekt: {project_name}.
Bitte merge alles zu EINER finalen, sauberen Markdown-Dokumentation.

Struktur-Vorschlag:
1) Überblick / Zweck
2) Architektur / Komponenten
3) Projektstruktur / Module
4) Setup (env, config, docker)
5) Hauptflows / Datenfluss
6) API/Services/Agents (falls vorhanden)
7) Wichtige Klassen/Funktionen
8) Erweiterung / TODO / Hinweise

Projekt Tree:
{project_tree}

PARTIAL DOCS:
{merged_input}
""".strip()

    resp = client.chat.completions.create(
        model=MODEL,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )
    return resp.choices[0].message.content


# ---------------------------
# MAIN
# ---------------------------

def main():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY. Put it in .env or environment variables.")

    client = OpenAI(api_key=api_key)

    root = Path(os.getcwd()).resolve()
    project_name = root.name

    print(f"[INFO] Scanning project: {project_name}")
    files = collect_project_files(root)
    if not files:
        print("[WARN] No files found. Check INCLUDE_EXTENSIONS or ignore rules.")
        return

    print(f"[INFO] Found {len(files)} files.")
    project_tree = build_project_tree(files, root)

    # Read files
    file_contents: List[Tuple[str, str]] = []
    for fp in files:
        rel = str(fp.relative_to(root))
        content = safe_read_text(fp)
        file_contents.append((rel, content))

    # Chunking
    chunks = chunk_files(file_contents)
    print(f"[INFO] Created {len(chunks)} code chunks for LLM.")

    partial_docs: List[str] = []
    for i, chunk in enumerate(chunks, start=1):
        print(f"[INFO] Generating docs chunk {i}/{len(chunks)} ...")
        doc_part = call_openai_for_docs(
            client=client,
            project_name=project_name,
            project_tree=project_tree,
            chunk_text=chunk,
            chunk_index=i,
            chunk_count=len(chunks),
        )
        partial_docs.append(doc_part)

        # Optional: save partial results
        part_hash = sha256_text(doc_part)
        Path("docs_parts").mkdir(exist_ok=True)
        Path("docs_parts") / f"part_{i:02d}_{part_hash}.md"
        (Path("docs_parts") / f"part_{i:02d}_{part_hash}.md").write_text(doc_part, encoding="utf-8")

    print("[INFO] Merging partial documentation into final Markdown...")
    final_doc = call_openai_merge(
        client=client,
        partial_docs=partial_docs,
        project_name=project_name,
        project_tree=project_tree,
    )

    out_path = Path("DOCUMENTATION.md")
    out_path.write_text(final_doc, encoding="utf-8")

    print(f"[DONE] Documentation generated: {out_path.resolve()}")
    print("[NOTE] Partial docs are saved under ./docs_parts/")


if __name__ == "__main__":
    main()
