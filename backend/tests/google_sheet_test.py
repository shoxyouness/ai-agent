# test.py
# One-file smoke test for the Python MCP Google Sheets server:
# - Starts MCP server via `uvx google-sheets-mcp@latest`
# - Lists available tools
# - Ensures a "contacts" tab with headers
# - Upserts a sample contact
# - Fuzzy finds "Younes" and resolves an email
#
# Prereqs:
#   pip install "mcp>=0.1.0" langchain-mcp-adapters python-dotenv rapidfuzz
#   Install uv (https://astral.sh/uv) so `uvx` is available
#   Enable Google Sheets & Drive APIs; create Service Account & JSON
#   Share your target spreadsheet with the service account email as Editor
#
# .env (minimal):
#   CONTACTS_SHEET_ID=1abcDEF...  (the ID from the sheet URL)
#   # EITHER paste the 6 fields directly:
#   # project_id=...
#   # private_key_id=...
#   # private_key=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n
#   # client_email=...@....iam.gserviceaccount.com
#   # client_id=...
#   # client_x509_cert_url=https://www.googleapis.com/robot/v1/metadata/x509/...
#   # OR point to the JSON and we’ll read those fields:
#   # GOOGLE_APPLICATION_CREDENTIALS=C:/path/to/service-account.json
#
# Run:  python test.py

import os, json, uuid, asyncio, difflib
from pprint import pprint
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools

load_dotenv()

TAB = "contacts"
HEADERS = [
    "id","full_name","aliases","primary_email","other_emails","phones",
    "relation","tone","language","org","timezone","notes","last_contacted","source"
]

# Globals assigned at runtime after introspecting tool names
TOOL = {}

# -------- service-account JSON fallback helpers --------
def load_sa_fields():
    p = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if p and os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

SA = load_sa_fields()

def env_or_sa(name: str):
    """Get a value from environment or, if missing, from the service-account JSON."""
    return os.getenv(name) or SA.get(name)

# -------------------------------------------------------

def need(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing env: {name}")
    return v

def row_to_dict(row: list[str]) -> dict:
    data = list(row) + [""] * (len(HEADERS) - len(row))
    return dict(zip(HEADERS, data))

def dict_to_row(d: dict) -> list[str]:
    out = []
    for h in HEADERS:
        v = d.get(h, "")
        if isinstance(v, (list, tuple)):
            v = json.dumps(v, ensure_ascii=False)
        out.append(v)
    return out

def best_fuzzy_idx(query: str, candidates: list[str]) -> int | None:
    if not candidates: return None
    scores = [difflib.SequenceMatcher(None, query.lower(), c.lower()).ratio() for c in candidates]
    i = max(range(len(scores)), key=scores.__getitem__)
    return i if scores[i] >= 0.7 else None

def pick_tool(toolmap: dict[str, object], preferred: list[str], fallbacks: list[str]) -> object | None:
    # exact first
    for n in preferred:
        if n in toolmap: return toolmap[n]
    # then substring contains (case-insensitive)
    lower = {k.lower(): v for k, v in toolmap.items()}
    for sub in fallbacks:
        for k in lower:
            if sub in k:
                return lower[k]
    return None

def get_all_rows(spreadsheet_id: str) -> list[list[str]]:
    """Read A2:.. from contacts sheet using whichever 'get values' tool exists."""
    t = TOOL["get_values"]
    resp = t.invoke({"spreadsheetId": spreadsheet_id, "range": f"{TAB}!A2:{chr(ord('A')+len(HEADERS)-1)}"})
    if isinstance(resp, dict):
        return resp.get("values", []) or []
    return resp or []

def ensure_sheet_and_headers(spreadsheet_id: str):
    meta = TOOL["get_metadata"].invoke({"spreadsheetId": spreadsheet_id})
    sheet_names = []
    if isinstance(meta, dict):
        for s in meta.get("sheets", []) or []:
            props = s.get("properties", {})
            title = props.get("title")
            if title: sheet_names.append(title)

    if TAB not in sheet_names:
        TOOL["insert_sheet"].invoke({"spreadsheetId": spreadsheet_id, "properties": {"title": TAB}})

    existing = TOOL["get_values"].invoke({"spreadsheetId": spreadsheet_id, "range": f"{TAB}!A1:{chr(ord('A')+len(HEADERS)-1)}1"})
    have = False
    if isinstance(existing, dict):
        vals = existing.get("values", [])
        have = bool(vals and vals[0] and vals[0][0] == "id")
    elif isinstance(existing, list):
        have = bool(existing and existing[0] and existing[0][0] == "id")

    if not have:
        TOOL["update_values"].invoke({
            "spreadsheetId": spreadsheet_id,
            "range": f"{TAB}!A1",
            "values": [HEADERS],
            "valueInputOption": "USER_ENTERED",
        })

def upsert_contact(spreadsheet_id: str, contact: dict) -> str:
    rows = get_all_rows(spreadsheet_id)

    c = {**contact}
    if not c.get("id"):
        c["id"] = str(uuid.uuid4())

    target = (c.get("primary_email") or "").strip().lower()
    idx = None
    for i, r in enumerate(rows):
        pe = (r[3] if len(r) > 3 else "").strip().lower()
        if target and pe == target:
            idx = i
            break

    row = dict_to_row(c)

    if idx is None:
        TOOL["append_values"].invoke({
            "spreadsheetId": spreadsheet_id,
            "range": f"{TAB}!A2",
            "values": [row],
            "valueInputOption": "USER_ENTERED",
        })
        return c["id"]
    else:
        start_col = "A"
        end_col = chr(ord("A")+len(HEADERS)-1)
        TOOL["update_values"].invoke({
            "spreadsheetId": spreadsheet_id,
            "range": f"{TAB}!{start_col}{idx+2}:{end_col}{idx+2}",
            "values": [row],
            "valueInputOption": "USER_ENTERED",
        })
        return c["id"]

def find_contact(spreadsheet_id: str, query: str) -> dict:
    rows = get_all_rows(spreadsheet_id)
    dicts = [row_to_dict(r) for r in rows]
    if not dicts: return {}
    keys = []
    for d in dicts:
        keys.append(" | ".join(x for x in [
            d.get("full_name") or "",
            d.get("primary_email") or "",
            d.get("aliases") or "",
            d.get("org") or "",
        ] if x))
    i = best_fuzzy_idx(query, keys)
    return dicts[i] if i is not None else {}

def get_contact_email(spreadsheet_id: str, name_or_email: str) -> str:
    c = find_contact(spreadsheet_id, name_or_email)
    if not c:
        if "@" in (name_or_email or ""):
            return name_or_email
        return ""
    if c.get("primary_email"): return c["primary_email"]
    try:
        others = json.loads(c.get("other_emails") or "[]")
        return (others[0] if others else "") or ""
    except Exception:
        return ""

async def main():
    sheet_id = need("CONTACTS_SHEET_ID")

    # ✅ Use env_or_sa() so we can read from .env OR the JSON file via GOOGLE_APPLICATION_CREDENTIALS
    required = ["project_id","private_key_id","private_key","client_email","client_id","client_x509_cert_url"]
    server_env = {k: env_or_sa(k) for k in required}
    missing = [k for k,v in server_env.items() if not v]
    if missing:
        raise RuntimeError(
            f"Missing credentials for: {missing}. "
            "Set them in .env OR set GOOGLE_APPLICATION_CREDENTIALS to your service-account JSON."
        )

    print("\n[1/4] Starting Python Google Sheets MCP server via uvx...")
    params = StdioServerParameters(
        command="uvx",
        args=["google-sheets-mcp@latest"],
        env=server_env,
    )

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            tools = await load_mcp_tools(session)
            toolmap = {t.name: t for t in tools}
            print("Available tools:")
            for n in sorted(toolmap):
                print("  -", n)

            # Heuristically bind the common tools (names may vary slightly between releases)
            TOOL["get_values"]   = pick_tool(toolmap,
                                             ["sheets_get_values", "get_values"],
                                             ["get_values", "read", "values"])
            TOOL["update_values"] = pick_tool(toolmap,
                                              ["sheets_update_values", "update_values"],
                                              ["update", "set_values"])
            TOOL["append_values"] = pick_tool(toolmap,
                                              ["sheets_append_values", "append_values"],
                                              ["append"])
            TOOL["get_metadata"]  = pick_tool(toolmap,
                                              ["sheets_get_metadata", "get_metadata"],
                                              ["metadata", "properties"])
            TOOL["insert_sheet"]  = pick_tool(toolmap,
                                              ["sheets_insert_sheet", "insert_sheet", "create_sheet"],
                                              ["insert_sheet", "add_sheet", "create_sheet"])

            missing_tools = [k for k,v in TOOL.items() if v is None]
            if missing_tools:
                raise RuntimeError(f"Could not map required tools: {missing_tools}. "
                                   f"Check the printed tool list and update the name heuristics.")

            print("\n[2/4] Ensuring sheet & headers...")
            ensure_sheet_and_headers(sheet_id)
            print("   -> contacts tab ready ✔")

            print("[3/4] Upserting sample contact...")
            sample = {
                "full_name": "Younes Dahmani",
                "aliases": ["Younes","Y. Dahmani"],
                "primary_email": "younes.dahmani@example.com",
                "other_emails": ["y.dahmani@altmail.com"],
                "phones": ["+49 151 2345678"],
                "relation": "friend",
                "tone": "informal",
                "language": "de",
                "org": "FH Dortmund",
                "timezone": "Europe/Berlin",
                "notes": "Prefers short emails.",
                "source": "manual",
            }
            cid = upsert_contact(sheet_id, sample)
            print(f"   -> id: {cid}")

            print("[4/4] Lookup & resolve email...")
            best = find_contact(sheet_id, "Younes")
            print("   find_contact('Younes') ->")
            pprint(best)
            email = get_contact_email(sheet_id, "Younes")
            print(f"   get_contact_email('Younes') -> {email or '(not found)'}")

            print("\nDone. Open the spreadsheet to verify the row.")

if __name__ == "__main__":
    # Debug: show which critical vars are visible (env or JSON)
    print("DEBUG env:", {
        "project_id": env_or_sa("project_id"),
        "client_email": env_or_sa("client_email"),
        "CONTACTS_SHEET_ID": os.getenv("CONTACTS_SHEET_ID"),
        "from_json": bool(SA),
    })
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
