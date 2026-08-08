```markdown
# Feature 15 — CSV Upload Route Wiring

**Status:** Spec finalized — ready for code.
**Boundary:** `backend/projects/` only (two new routes added to the existing `backend/projects/router.py`, consuming Feature 13's `backend/csv/parser.py`, `validator.py`, and `template.py` as-is). Does not modify `backend/csv/` itself, `backend/calculation/`, or any frontend directory.
**Depends on:** Feature 13 (`backend/csv/parser.py`'s `parse_csv_bytes`/`CsvStructureError`, `backend/csv/validator.py`'s `validate_rows`, `backend/csv/models.py`'s `CsvValidationResult`, `backend/csv/template.py`'s `generate_template_csv` — all already built and verified), Feature 12 (`backend/projects/repository.py`'s `get_project`/`replace_project` — reused as-is, no new repository function needed).

---

## 1. What this unit delivers

This is the deferred piece from Feature 13's spec:
> Wiring a `POST /projects/{id}/loads/csv-upload` route ... deliberately deferred out of Feature 13 since it touches a second backend module (split rule).

Two routes, both thin wrappers around already-built logic — no new calculation, parsing, or validation logic is written in this unit:

1. **`GET /api/projects/csv-template`** — streams Feature 13's `generate_template_csv()` output as a downloadable file. Stateless, no project context needed.
2. **`POST /api/projects/{project_id}/loads/csv-upload`** — accepts an uploaded CSV file, runs it through Feature 13's `parser.py` → `validator.py` pipeline, and either commits valid rows to the project (only if the file is 100% valid) or returns a clear rejection pointing the user back to the template — see §4.

**Explicitly NOT in this unit:**
- Any change to `backend/csv/parser.py` or `validator.py` — used exactly as Feature 13 built them.
- Any frontend upload button / file picker UI — backend-only.
- Resolving `power_factor` further — still `backend/calculation/load.py`'s job, unchanged.

---

## 2. Verified behavior — reusing Feature 13 exactly as built

Confirmed against the real `backend/csv/` source from Feature 13 (no re-guessing):

| Function | Signature | Behavior this route relies on |
|---|---|---|
| `parse_csv_bytes(file_bytes: bytes) -> pd.DataFrame` | raises `CsvStructureError` on empty file / bad headers | Route must catch `CsvStructureError` and return a 400-level error with `.message`, not let it become an unhandled 500 |
| `validate_rows(df: pd.DataFrame) -> CsvValidationResult` | never raises — always returns a result with `valid_rows`/`invalid_rows` split | Route calls it and inspects `invalid_count` to decide commit vs. reject |
| `generate_template_csv() -> bytes` | static, deterministic | Route wraps this in a `Response` with the right `Content-Type`/`Content-Disposition` headers for a file download |

---

## 3. Decision — strict all-or-nothing commit, with a template pointer on rejection

Per your instruction: if the file isn't valid, the user is told to fix it and re-upload — with the template download as the reference to remove any ambiguity about the expected format. No partial commit exists in this unit.

This resolves the earlier open question cleanly:
- **`invalid_count == 0`** → all valid rows are committed to the project immediately. No separate `commit=true` flag needed — a fully valid file just succeeds.
- **`invalid_count > 0`** → **nothing is saved**. The response returns the full `CsvValidationResult` (so the user can see exactly which rows/fields failed and why) **plus a `template_url` field** pointing at `GET /api/projects/csv-template`, so the fix-and-retry path is explicit and self-contained — the user doesn't have to go hunting for the correct format separately.

This also removes the need for a `commit` query parameter entirely — the endpoint has exactly one behavior per outcome, which is simpler and matches "ask the user to fix and re-upload" as the only path, per your instruction.

---

## 4. Append vs. Replace — resolved per industry standard

Standard practice for CSV import in comparable tools (Notion, Airtable, Google Sheets import, Salesforce data import) is **additive/append by default** — an import adds records to what's already there, it does not silently wipe existing data. A destructive replace is something these tools always require as a separate, explicit action (e.g. "replace existing data" as its own checkbox), never the default.

**Resolved: Append.** Valid rows from the CSV are added to the project's existing `loads` list. This also matches `project-overview.md`'s Core User Flow step 3, which frames manual entry and CSV upload as two complementary ways to build up the same load list, not mutually exclusive modes.

A future "replace all loads from CSV" action, if ever needed, would be a distinct, explicitly-named endpoint — not silently bundled into this one.

---

## 5. Endpoints

Added to the existing `backend/projects/router.py`.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/csv-template` | Downloads the CSV template (Feature 13's `template.py`) |
| `POST` | `/api/projects/{project_id}/loads/csv-upload` | Uploads + validates a CSV against `LoadItem`. Commits (appends to `loads`) only if every row is valid; otherwise rejects with a per-row report and a template link. |

### 5.1 Request shape — upload endpoint

`multipart/form-data` with a single `file` field (standard FastAPI `UploadFile` pattern):

```
POST /api/projects/{project_id}/loads/csv-upload
Content-Type: multipart/form-data
file: <the .csv file>
```

### 5.2 Response shape — upload endpoint

**On structural failure** (`CsvStructureError` — empty file, wrong headers): HTTP 400, with a message and a `template_url` pointing to the template download, so the very first failure mode also guides the user to the correct format.

**On row-level failure** (`invalid_count > 0`): HTTP 200 (the request was processed, just not committed), body:
```json
{
  "committed": false,
  "template_url": "/api/projects/csv-template",
  "validation_result": { /* full CsvValidationResult */ }
}
```

**On full success** (`invalid_count == 0`): HTTP 200, body:
```json
{
  "committed": true,
  "loads_added": 0,
  "project": { /* updated Project, via repository.replace_project */ }
}
```

### 5.3 Defensive limits (not business rules — just reasonable guards)

- Max upload size: 5 MB.
- Max rows: 10,000.
Both rejected with a clear 400 message before parsing proceeds, since neither is a formula or engineering constraint — purely a safeguard against accidental huge uploads, consistent with how `code-standards.md` expects specific, clear error messages rather than a silent hang or crash.

- Light file-extension check (`.csv`) before attempting to parse, purely for a friendlier error message — `parse_csv_bytes`'s existing structural checks would already reject a non-CSV file's content, so this is not a security boundary, just better UX (a `.txt` or `.xlsx` upload gets a message about the file type, not a generic parsing error).

---

## 6. Verification plan (per `ai-workflow-rules.md`'s "Before Moving to the Next Unit")

- `GET /csv-template`: confirm the downloaded bytes are byte-identical to calling `generate_template_csv()` directly, with correct `Content-Type: text/csv` and a sensible filename in `Content-Disposition`.
- Upload with an all-valid CSV: confirm the project's `loads` grows by exactly the number of valid rows (append, not replace), confirm `updated_at`/`version_history` update (via `replace_project`, unconditional per Feature 12).
- Upload with at least one invalid row: confirm the project's `loads` in the database are **unchanged**, confirm the response has `committed: false`, a `template_url`, and the full per-row `validation_result` matching what Feature 13's own validator would produce.
- Upload a malformed file (bad headers, empty): confirm a clear 400 error with a `template_url`, not a raw 500.
- Upload a file exceeding the size/row limits: confirm a clear, specific rejection message before any parsing is attempted.
- Confirm no formula, PF-resolution, or calculation logic was added anywhere in this unit — it only parses/validates/appends, exactly reusing Feature 13's functions.
```