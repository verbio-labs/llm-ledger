"""LLM Ledger core — zero-dependency claim parsing, validation, and search.

Pure Python 3 stdlib. Used by the `ledger` CLI and the MCP server.
The claim YAML is a small, regular subset, so we parse it directly instead
of pulling in PyYAML (keeps the repo dependency-free).
"""

from __future__ import annotations

import os
import re
import glob
from datetime import date

ENUM_TYPE = {"fact", "event", "definition", "claim", "metric", "relation"}
ENUM_CONFIDENCE = {"high", "medium", "low", "contested"}
ENUM_STATUS = {"active", "superseded", "contested", "retracted"}
REQUIRED = ["id", "statement", "topic", "type", "sources", "confidence", "status"]

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CLAIM_ID_RE = re.compile(r"clm-\d{4}-\d{4,}")


# --------------------------------------------------------------------------- #
# Minimal YAML-subset parser (only what claim blocks use)
# --------------------------------------------------------------------------- #
def _scalar(v: str):
    v = v.strip()
    if v == "" or v == "null" or v == "~":
        return None
    if v in ("[]",):
        return []
    if v.startswith("[") and v.endswith("]"):
        inner = v[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(x.strip()) for x in inner.split(",")]
    return _strip_quotes(v)


def _strip_quotes(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        return v[1:-1]
    return v


def parse_block(text: str) -> dict:
    """Parse one claim YAML block into a dict."""
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        if not raw.strip() or raw.lstrip().startswith("#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", raw)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2)
        if val.strip() == "" and i + 1 < len(lines) and lines[i + 1].lstrip().startswith("- "):
            # list of mappings (sources) or list of scalars
            items = []
            i += 1
            cur = None
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].startswith("\t")):
                item_line = lines[i]
                stripped = item_line.strip()
                if stripped.startswith("- "):
                    if cur is not None:
                        items.append(cur)
                    rest = stripped[2:]
                    sub = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", rest)
                    if sub:
                        cur = {sub.group(1): _scalar(sub.group(2))}
                    else:
                        cur = _scalar(rest)
                else:
                    sub = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", stripped)
                    if sub and isinstance(cur, dict):
                        cur[sub.group(1)] = _scalar(sub.group(2))
                i += 1
            if cur is not None:
                items.append(cur)
            out[key] = items
            continue
        out[key] = _scalar(val)
        i += 1
    return out


def extract_yaml_blocks(md_text: str):
    """Yield the contents of every ```yaml fenced block in a markdown file."""
    return re.findall(r"```yaml\s*\n(.*?)```", md_text, re.DOTALL)


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def load_claims(repo_root: str):
    """Return (claims, errors). claims is a list of dicts with `_file` added."""
    claims = []
    errors = []
    pattern = os.path.join(repo_root, "30-ledger", "claims", "*.md")
    for path in sorted(glob.glob(pattern)):
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        rel = os.path.relpath(path, repo_root)
        for block in extract_yaml_blocks(text):
            try:
                claim = parse_block(block)
                claim["_file"] = rel
                claims.append(claim)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{rel}: failed to parse a claim block ({exc})")
    return claims, errors


def _is_date(v) -> bool:
    return isinstance(v, str) and bool(_DATE_RE.match(v))


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def validate(repo_root: str):
    """Return list of (severity, message). severity in {ERROR, WARN, INFO}."""
    issues = []
    claims, parse_errors = load_claims(repo_root)
    for e in parse_errors:
        issues.append(("ERROR", e))

    by_id = {}
    for c in claims:
        cid = c.get("id")
        loc = c.get("_file", "?")
        if not cid:
            issues.append(("ERROR", f"{loc}: claim missing 'id'"))
            continue
        if cid in by_id:
            issues.append(("ERROR", f"{loc}: duplicate claim id '{cid}'"))
        by_id[cid] = c

    for c in claims:
        cid = c.get("id", "?")
        loc = c.get("_file", "?")

        # required fields
        for field in REQUIRED:
            if c.get(field) in (None, "", []) and field != "sources":
                issues.append(("ERROR", f"{cid}: missing required field '{field}'"))
        # enums
        if c.get("type") not in ENUM_TYPE:
            issues.append(("ERROR", f"{cid}: invalid type '{c.get('type')}'"))
        if c.get("confidence") not in ENUM_CONFIDENCE:
            issues.append(("ERROR", f"{cid}: invalid confidence '{c.get('confidence')}'"))
        if c.get("status") not in ENUM_STATUS:
            issues.append(("ERROR", f"{cid}: invalid status '{c.get('status')}'"))

        # sources required + provenance
        sources = c.get("sources") or []
        if not sources:
            issues.append(("ERROR", f"{cid}: no sources (every claim needs provenance)"))
        for s in sources:
            if not isinstance(s, dict) or not s.get("ref"):
                issues.append(("ERROR", f"{cid}: a source is missing 'ref'"))
                continue
            ref = s["ref"]
            if ref == "model-prior":
                if c.get("confidence") != "low":
                    issues.append(("WARN", f"{cid}: model-prior source should be confidence:low"))
                continue
            if not os.path.exists(os.path.join(repo_root, ref)):
                issues.append(("ERROR", f"{cid}: source ref not found -> {ref}"))

        # temporal consistency
        vf, vu = c.get("valid_from"), c.get("valid_until")
        if _is_date(vf) and _is_date(vu) and vf > vu:
            issues.append(("ERROR", f"{cid}: valid_from ({vf}) is after valid_until ({vu})"))

        # supersession integrity
        status = c.get("status")
        sb, sup = c.get("superseded_by"), c.get("supersedes")
        if status == "superseded":
            if not sb:
                issues.append(("ERROR", f"{cid}: status superseded but no superseded_by"))
            elif sb not in by_id:
                issues.append(("ERROR", f"{cid}: superseded_by points to missing '{sb}'"))
            elif by_id[sb].get("supersedes") != cid:
                issues.append(("ERROR", f"{cid}: supersession not reciprocal with {sb}"))
        if sup:
            if sup not in by_id:
                issues.append(("ERROR", f"{cid}: supersedes points to missing '{sup}'"))
            elif by_id[sup].get("superseded_by") != cid:
                issues.append(("ERROR", f"{cid}: supersedes target {sup} doesn't point back"))

        # contested integrity
        if status == "contested" and not (c.get("contradicts") or []):
            issues.append(("WARN", f"{cid}: status contested but contradicts is empty"))
        for other in (c.get("contradicts") or []):
            if other not in by_id:
                issues.append(("ERROR", f"{cid}: contradicts missing claim '{other}'"))

    # footnote + claim_refs integrity in topic views
    for path in sorted(glob.glob(os.path.join(repo_root, "30-ledger", "topics", "*.md"))):
        with open(path, encoding="utf-8") as fh:
            t = fh.read()
        rel = os.path.relpath(path, repo_root)
        for ref in set(re.findall(r"\[\^(clm-\d{4}-\d{4,})\]", t)):
            if ref not in by_id:
                issues.append(("ERROR", f"{rel}: footnote references missing claim '{ref}'"))

    # index drift (lenient)
    bt = os.path.join(repo_root, "30-ledger", "indexes", "by-topic.md")
    if os.path.exists(bt):
        with open(bt, encoding="utf-8") as fh:
            for cref in set(_CLAIM_ID_RE.findall(fh.read())):
                if cref not in by_id:
                    issues.append(("WARN", f"by-topic.md: lists unknown claim '{cref}'"))

    # orphan claims (active claims not cited by any topic view)
    cited = set()
    for path in glob.glob(os.path.join(repo_root, "30-ledger", "topics", "*.md")):
        with open(path, encoding="utf-8") as fh:
            cited |= set(re.findall(r"clm-\d{4}-\d{4,}", fh.read()))
    for c in claims:
        if c.get("status") == "active" and c.get("id") not in cited:
            issues.append(("WARN", f"{c.get('id')}: active claim not cited by any topic view"))

    return issues, claims


# --------------------------------------------------------------------------- #
# Search (simple, zero-dep retrieval primitive for the MCP server)
# --------------------------------------------------------------------------- #
def search(claims, query: str, as_of: str | None = None, limit: int = 8):
    """Keyword-overlap ranking with active/high boosts and optional as-of filter."""
    terms = [t for t in re.split(r"\W+", query.lower()) if len(t) > 1]
    scored = []
    for c in claims:
        if as_of and _is_date(as_of):
            vf, vu = c.get("valid_from"), c.get("valid_until")
            if _is_date(vf) and as_of < vf:
                continue
            if _is_date(vu) and as_of >= vu:
                continue
        hay = " ".join(
            str(c.get(k, "")) for k in ("statement", "topic", "type")
        ).lower()
        score = sum(hay.count(t) for t in terms)
        if score == 0:
            continue
        if c.get("status") == "active":
            score += 2
        if c.get("confidence") == "high":
            score += 1
        if c.get("status") == "contested":
            score += 1  # surface disputes
        scored.append((score, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:limit]]
