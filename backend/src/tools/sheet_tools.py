import os
import json
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from dotenv import load_dotenv
from pydantic import BaseModel, Field, EmailStr
from langchain.tools import tool
import gspread

# =========================
# Config / Schema
# =========================

COLUMNS = [
    "name",
    "email",
    "phone",
    "tone",                 # "formal" | "informal" | "friendly"
    "salutation",           # e.g., "Hi Younes", "Hallo Herr Dahmani"
    "how_to_talk",          # free text, e.g., "like a friend, casual, uses emojis"
    "preferred_channel",    # "email" | "whatsapp" | "sms" | "phone"
    "locale",               # e.g., "de-DE", "en-US", "fr-FR"
    "company",
    "role",
    "tags",                 # comma-separated labels
    "notes",
    "last_contacted",       # ISO date string
    "created_at",           # ISO datetime string
    "updated_at",           # ISO datetime string
]

class ContactField(str, Enum):
    name = "name"
    email = "email"
    phone = "phone"
    tone = "tone"
    salutation = "salutation"
    how_to_talk = "how_to_talk"
    preferred_channel = "preferred_channel"
    locale = "locale"
    company = "company"
    role = "role"
    tags = "tags"
    notes = "notes"
    last_contacted = "last_contacted"
    created_at = "created_at"
    updated_at = "updated_at"

load_dotenv()

# =========================
# Helpers
# =========================

def _get_ws():
    sheet_id = os.getenv("GOOGLE_SHEETS_SHEET_ID", "").strip()
    ws_title = os.getenv("GOOGLE_SHEETS_WORKSHEET_TITLE", "Contacts").strip()

    if not sheet_id:
        raise RuntimeError("Missing GOOGLE_SHEETS_SHEET_ID.")

    # read keys exactly as in your .env
    private_key = (os.getenv("private_key", "") or "").strip()
    private_key = private_key.replace("\\n", "\n")  # important

    creds_dict = {
        "type": os.getenv("type", "service_account"),
        "project_id": os.getenv("project_id"),
        "private_key_id": os.getenv("private_key_id"),
        "private_key": private_key,
        "client_email": os.getenv("client_email"),
        "client_id": os.getenv("client_id"),
        "auth_uri": os.getenv("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": os.getenv("token_uri", "https://oauth2.googleapis.com/token"),
        "auth_provider_x509_cert_url": os.getenv(
            "auth_provider_x509_cert_url",
            "https://www.googleapis.com/oauth2/v1/certs",
        ),
        "client_x509_cert_url": os.getenv("client_x509_cert_url", ""),
        "universe_domain": os.getenv("universe_domain", "googleapis.com"),
    }

    required = ["project_id", "private_key_id", "private_key", "client_email", "client_id"]
    missing = [k for k in required if not creds_dict.get(k)]
    if missing:
        raise RuntimeError(f"Missing Google service account env vars: {missing}")

    gc = gspread.service_account_from_dict(creds_dict)
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet(ws_title)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=ws_title, rows=100, cols=max(20, len(COLUMNS)))
        ws.append_row(COLUMNS)

    # header fix
    header = ws.row_values(1)
    if [h.strip().lower() for h in header] != COLUMNS:
        if not header:
            ws.update(f"A1:{gspread.utils.rowcol_to_a1(1, len(COLUMNS))}", [COLUMNS])
        else:
            ws.resize(rows=max(ws.row_count, 2), cols=max(ws.col_count, len(COLUMNS)))
            ws.update(f"A1:{gspread.utils.rowcol_to_a1(1, len(COLUMNS))}", [COLUMNS])

    return ws

def _normalize_email(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    return s.strip().lower()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _row_to_dict(row: List[str]) -> Dict[str, Any]:
    data = {COLUMNS[i]: (row[i] if i < len(row) else "") for i in range(len(COLUMNS))}
    data["email"] = _normalize_email(data.get("email", ""))
    return data


def _dict_to_row(d: Dict[str, Any]) -> List[str]:
    return [str(d.get(col, "") or "") for col in COLUMNS]


def _find_row_indices(ws, predicate) -> List[int]:
    """Return 1-based row indices (including header row as 1) that match predicate(row_dict)."""
    values = ws.get_all_values()
    rows = []
    for idx, row in enumerate(values, start=1):
        if idx == 1:
            continue  # skip header
        rowd = _row_to_dict(row)
        if predicate(rowd):
            rows.append(idx)
    return rows


def _find_first_row_by_identifier(ws, identifier: str) -> Optional[int]:
    """Identifier can be an email or a name (case-insensitive). Prefer exact email match."""
    ident = identifier.strip()
    ident_lower = ident.lower()

    # Try exact email match first
    matches = _find_row_indices(ws, lambda d: d.get("email") == ident_lower)
    if matches:
        return matches[0]

    # Fallback: name case-insensitive exact match
    matches = _find_row_indices(ws, lambda d: d.get("name", "").strip().lower() == ident_lower)
    return matches[0] if matches else None

# =========================
# Pydantic Schemas for Tools
# =========================

class Contact(BaseModel):
    name: str = Field(..., description="Display name of the person")
    email: Optional[EmailStr] = Field(None, description="Email address")
    phone: Optional[str] = Field(None, description="Phone number in free format")
    tone: Optional[str] = Field("friendly", description='Preferred tone: "formal", "informal", or "friendly"')
    salutation: Optional[str] = Field(None, description='Greeting line, e.g., "Hi Younes"')
    how_to_talk: Optional[str] = Field(None, description="Guidance on style, e.g., 'like a friend, casual'")
    preferred_channel: Optional[str] = Field("email", description='One of: "email", "whatsapp", "sms", "phone"')
    locale: Optional[str] = Field(None, description='BCP47, e.g., "de-DE", "en-US", "fr-FR"')
    company: Optional[str] = None
    role: Optional[str] = None
    tags: Optional[List[str]] = Field(default=None, description="List of labels")
    notes: Optional[str] = None
    last_contacted: Optional[str] = Field(None, description="ISO date (YYYY-MM-DD)")
    # created_at / updated_at are set server-side


class GetContactArgs(BaseModel):
    identifier: str = Field(..., description="Email or exact name (case-insensitive for name).")


class ListContactsArgs(BaseModel):
    query: Optional[str] = Field(None, description="Substring to search in name/email/tags/company/role")
    tag: Optional[str] = Field(None, description="Filter by tag (case-insensitive exact match)")
    limit: int = Field(20, ge=1, le=200, description="Max number of rows to return")


class UpdateFieldArgs(BaseModel):
    identifier: str = Field(..., description="Email or exact name")
    field: ContactField = Field(..., description="Field name to update")
    value: str = Field(..., description="New value")


class SetToneArgs(BaseModel):
    identifier: str = Field(..., description="Email or exact name")
    tone: str = Field(..., description='Preferred tone: "formal", "informal", or "friendly"')


class DeleteContactArgs(BaseModel):
    identifier: str = Field(..., description="Email or exact name")

# =========================
# Tools
# =========================

@tool("upsert_contact", args_schema=Contact)
def upsert_contact(
    name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    tone: Optional[str] = "friendly",
    salutation: Optional[str] = None,
    how_to_talk: Optional[str] = None,
    preferred_channel: Optional[str] = "email",
    locale: Optional[str] = None,
    company: Optional[str] = None,
    role: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
    last_contacted: Optional[str] = None,
) -> str:
    """
    Create or update a contact in Google Sheets. Matches by email first, then by exact name.
    If found, updates fields; if not, appends a new row.
    """
    try:
        ws = _get_ws()

        data = {
            "name": name.strip(),
            "email": _normalize_email(email) if email else "",
            "phone": (phone or "").strip(),
            "tone": (tone or "friendly").strip(),
            "salutation": (salutation or "").strip(),
            "how_to_talk": (how_to_talk or "").strip(),
            "preferred_channel": (preferred_channel or "email").strip(),
            "locale": (locale or "").strip(),
            "company": (company or "").strip(),
            "role": (role or "").strip(),
            "tags": ",".join(tags) if tags else "",
            "notes": (notes or "").strip(),
            "last_contacted": (last_contacted or "").strip(),
            "created_at": "",
            "updated_at": "",
        }

        now = _now_iso()
        identifier = data["email"] or data["name"]
        row_idx = _find_first_row_by_identifier(ws, identifier)

        if row_idx:
            existing = _row_to_dict(ws.row_values(row_idx))
            merged = {**existing, **{k: v for k, v in data.items() if v != ""}}
            merged["updated_at"] = now
            if not existing.get("created_at"):
                merged["created_at"] = now

            ws.update(
                f"A{row_idx}:{gspread.utils.rowcol_to_a1(row_idx, len(COLUMNS))}",
                [_dict_to_row(merged)],
            )
            return f"Updated contact '{merged['name']}' (row {row_idx})."
        else:
            data["created_at"] = now
            data["updated_at"] = now
            ws.append_row(_dict_to_row(data))
            return f"Inserted new contact '{data['name']}'."
    except Exception as e:
        return f"Error in upsert_contact: {e}"


@tool("get_contact", args_schema=GetContactArgs)
def get_contact(identifier: str) -> Dict[str, Any]:
    """Return a single contact (as a dict) by email or exact name. If not found, returns {}."""
    try:
        ws = _get_ws()
        row_idx = _find_first_row_by_identifier(ws, identifier)
        if not row_idx:
            return {}
        return _row_to_dict(ws.row_values(row_idx))
    except Exception as e:
        return {"error": f"Error in get_contact: {e}"}


@tool("list_contacts", args_schema=ListContactsArgs)
def list_contacts(query: Optional[str] = None, tag: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
    """
    Search and return multiple contacts from Google Sheets.

    - If `query` is provided, it will perform a **case-insensitive substring search**
      across the following fields: name, email, company, role, and tags.
      Example: query="younes" will match "Younes Mhadhbi", "Younes Ben Ali",
      and also "younes@example.com".

    - If `tag` is provided, it will filter contacts by tag (case-insensitive exact match).
      Example: tag="friend" will return all contacts that have the tag "friend".

    - If both `query` and `tag` are provided, results must satisfy both filters.

    - Returns up to `limit` contacts (default: 20).

    Use this tool when you want to find **all matching contacts**, e.g.:
      - "List all contacts with the name Younes"
      - "Find everyone tagged as 'client'"
      - "Search for contacts from FH Dortmund"
    """
    try:
        ws = _get_ws()
        q = (query or "").strip().lower()
        t = (tag or "").strip().lower()

        out: List[Dict[str, Any]] = []
        for idx, row in enumerate(ws.get_all_values(), start=1):
            if idx == 1:
                continue
            d = _row_to_dict(row)

            ok = True
            if q:
                hay = " ".join([
                    d.get("name", ""),
                    d.get("email", "") or "",
                    d.get("company", "") or "",
                    d.get("role", "") or "",
                    d.get("tags", "") or "",
                ]).lower()
                ok = q in hay

            if ok and t:
                tags = [x.strip().lower() for x in (d.get("tags") or "").split(",") if x.strip()]
                ok = t in tags

            if ok:
                out.append(d)
                if len(out) >= limit:
                    break
        return out
    except Exception as e:
        return [{"error": f"Error in list_contacts: {e}"}]


@tool("update_contact_field", args_schema=UpdateFieldArgs)
def update_contact_field(identifier: str, field: ContactField, value: str) -> str:
    """Update exactly one field for a contact identified by email or name."""
    try:
        ws = _get_ws()
        row_idx = _find_first_row_by_identifier(ws, identifier)
        if not row_idx:
            return f"No contact found for '{identifier}'."

        current = _row_to_dict(ws.row_values(row_idx))
        current[field.value] = value
        current["updated_at"] = _now_iso()
        ws.update(
            f"A{row_idx}:{gspread.utils.rowcol_to_a1(row_idx, len(COLUMNS))}",
            [_dict_to_row(current)],
        )
        return f"Updated '{field.value}' for '{current['name']}'."
    except Exception as e:
        return f"Error in update_contact_field: {e}"


@tool("set_contact_tone", args_schema=SetToneArgs)
def set_contact_tone(identifier: str, tone: str) -> str:
    """Convenience: set the tone for a contact."""
    try:
        return update_contact_field.func(identifier=identifier, field=ContactField.tone, value=tone)
    except Exception as e:
        return f"Error in set_contact_tone: {e}"


@tool("delete_contact", args_schema=DeleteContactArgs)
def delete_contact(identifier: str) -> str:
    """Delete a contact by email or exact name."""
    try:
        ws = _get_ws()
        row_idx = _find_first_row_by_identifier(ws, identifier)
        if not row_idx:
            return f"No contact found for '{identifier}'."
        ws.delete_rows(row_idx)
        return f"Deleted contact '{identifier}'."
    except Exception as e:
        return f"Error in delete_contact: {e}"

# Export for easy registration
GOOGLE_SHEETS_CONTACT_TOOLS = [
    upsert_contact,
    get_contact,
    list_contacts,
    update_contact_field,
    set_contact_tone,
    delete_contact,
]

# ============= Demo =============
if __name__ == "__main__":
    print("Testing Contacts Sheet Tools ...")
    print(
        upsert_contact.func(
            name="Younes Mhadhbi",
            email="younes@example.com",
            phone="+49 170 000000",
            tone="friendly",
            salutation="Hi Younes",
            how_to_talk="Like a friend, casual but concise",
            preferred_channel="email",
            locale="de-DE",
            company="FH Dortmund",
            role="Student",
            tags=["friend", "automotive"],
            notes="Prefers short emails; emojis okay",
            last_contacted="2025-09-01",
        )
    )
    print(get_contact.func(identifier="younes@example.com"))
    print(set_contact_tone.func(identifier="younes@example.com", tone="informal"))
    print(list_contacts.func(query="younes", limit=5))
    print(update_contact_field.func(identifier="younes@example.com", field=ContactField.phone, value="+49 171 222222"))
    print(delete_contact.func(identifier="Younes Mhadhbi"))
