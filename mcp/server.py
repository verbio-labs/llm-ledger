#!/usr/bin/env python3
"""LLM Ledger MCP server.

Exposes the ledger as Model Context Protocol tools so ANY MCP-compatible client
(Claude Desktop, Cursor, etc.) can use the same verifiable, time-aware memory —
not just Claude Code.

The client's own LLM does the reasoning (reading raw sources, deciding what to
store); this server provides the trustworthy primitives: search with as-of time
travel, validated writes, timelines, and audits.

Run:  LEDGER_ROOT=/path/to/llm-ledger python3 mcp/server.py
Deps: pip install -r mcp/requirements.txt
"""

from __future__ import annotations

import os
import re
import sys
import glob
from datetime import date

# locate repo root and import the zero-dep core
REPO_ROOT = os.environ.get("LEDGER_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))
import ledger_core as core  # noqa: E402

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover
    sys.stderr.write("Missing dependency. Run: pip install -r mcp/requirements.txt\n")
    raise

mcp = FastMCP("llm-ledger")


def _fmt(c: dict) -> str:
    flag = "" if c.get("status") == "active" else f" [{c.get('status')}]"
    vf, vu = c.get("valid_from"), c.get("valid_until")
    span = f"  (valid {vf or '?'} -> {vu or 'now'})" if (vf or vu) else ""
    src = (c.get("sources") or [{}])[0].get("ref", "?")
    return (f"{c.get('id')}{flag} [{c.get('confidence')}]{span}\n"
            f"  {c.get('statement')}\n  source: {src}")


@mcp.tool()
def ledger_search(query: str, as_of: str = "") -> str:
    """Search the ledger for claims matching a query.

    Set as_of to YYYY-MM-DD to time-travel: only claims that were valid on that
    date are returned (the ledger's killer feature). Every result carries its
    source and confidence — never invent facts beyond what is returned.
    """
    claims, _ = core.load_claims(REPO_ROOT)
    hits = core.search(claims, query, as_of=as_of or None)
    if not hits:
        return "No matching claims. Consider ingesting a source first."
    header = f"{len(hits)} claim(s)" + (f" valid as of {as_of}" if as_of else "")
    return header + "\n\n" + "\n\n".join(_fmt(c) for c in hits)


@mcp.tool()
def ledger_get_topic(topic: str) -> str:
    """Return the assembled topic view (prose with footnotes) for a topic slug."""
    path = os.path.join(REPO_ROOT, "30-ledger", "topics", f"{topic}.md")
    if not os.path.exists(path):
        return f"No topic '{topic}'. Use ledger_list_topics to see what exists."
    with open(path, encoding="utf-8") as fh:
        return fh.read()


@mcp.tool()
def ledger_timeline(topic: str, as_of: str = "") -> str:
    """Show how knowledge about a topic changed over time.

    With as_of (YYYY-MM-DD), reconstruct the snapshot that was true on that date.
    Includes superseded claims — that is the point of a timeline.
    """
    claims, _ = core.load_claims(REPO_ROOT)
    rows = [c for c in claims if c.get("topic") == topic]
    if not rows:
        return f"No claims for topic '{topic}'."
    rows.sort(key=lambda c: (c.get("valid_from") or "0000"))
    out = []
    for c in rows:
        vf, vu = c.get("valid_from"), c.get("valid_until")
        if as_of and core._is_date(as_of):
            if core._is_date(vf) and as_of < vf:
                continue
            if core._is_date(vu) and as_of >= vu:
                continue
        out.append(f"{vf or '?':>10} -> {vu or 'now':<10}  {c.get('id')}  {c.get('statement')}")
    title = f"{topic} timeline" + (f" (as of {as_of})" if as_of else "")
    return title + "\n" + "\n".join(out)


@mcp.tool()
def ledger_list_topics() -> str:
    """List every topic in the ledger with its claim count."""
    claims, _ = core.load_claims(REPO_ROOT)
    counts: dict = {}
    for c in claims:
        counts[c.get("topic")] = counts.get(c.get("topic"), 0) + 1
    if not counts:
        return "Ledger is empty."
    return "\n".join(f"{t}: {n} claim(s)" for t, n in sorted(counts.items()) if t)


@mcp.tool()
def ledger_ingest(title: str, content: str, source_url: str = "") -> str:
    """Save a raw source into 10-inbox (does NOT synthesize claims).

    The client should later read it and call ledger_add_claim for each fact.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "source"
    path = os.path.join(REPO_ROOT, "10-inbox", f"{slug}.md")
    header = f"---\nsource_url: {source_url or 'local'}\ningested: {date.today()}\nstatus: uncompiled\n---\n\n"
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(header + content + "\n")
    return f"Ingested -> 10-inbox/{slug}.md (uncompiled). Read it, then add_claim per fact."


def _next_id(claims) -> str:
    nums = [int(m.group(1)) for c in claims if (m := re.search(r"clm-\d{4}-(\d+)", c.get("id", "")))]
    return f"clm-{date.today().year}-{(max(nums) + 1) if nums else 1:04d}"


def _append_claim(topic: str, fields: dict) -> str:
    """Write a claim block to 30-ledger/claims/{topic}.md and return its id."""
    cid = fields["id"]
    block = ["```yaml", f"id: {cid}", f'statement: "{fields["statement"]}"',
             f"topic: {topic}", f"type: {fields.get('type', 'claim')}",
             "sources:", f"  - ref: {fields['source_ref']}"]
    if fields.get("source_quote"):
        block.append(f'    quote: "{fields["source_quote"]}"')
    block += [f"confidence: {fields.get('confidence', 'medium')}",
              f"valid_from: {fields.get('valid_from') or 'unknown'}",
              f"valid_until: {fields.get('valid_until') or 'null'}",
              f"status: {fields.get('status', 'active')}",
              f"supersedes: {fields.get('supersedes') or 'null'}",
              "superseded_by: null", "contradicts: []", "relations: []",
              f"created: {date.today()}", f"updated: {date.today()}",
              "note: null", "```", ""]
    path = os.path.join(REPO_ROOT, "30-ledger", "claims", f"{topic}.md")
    prefix = "" if os.path.exists(path) else f"# Claims — {topic}\n\n"
    sep = "\n---\n\n" if os.path.exists(path) else ""
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(prefix + sep + "\n".join(block))
    return cid


@mcp.tool()
def ledger_add_claim(
    statement: str,
    topic: str,
    source_ref: str,
    source_quote: str = "",
    type: str = "claim",
    confidence: str = "medium",
    valid_from: str = "",
    valid_until: str = "",
) -> str:
    """Append a validated claim to the ledger.

    Rejects the write if it fails validation (bad enum, missing/nonexistent
    source). Auto-assigns the next clm-YYYY-NNNN id.
    """
    if type not in core.ENUM_TYPE:
        return f"Rejected: type must be one of {sorted(core.ENUM_TYPE)}"
    if confidence not in core.ENUM_CONFIDENCE:
        return f"Rejected: confidence must be one of {sorted(core.ENUM_CONFIDENCE)}"
    if source_ref != "model-prior" and not os.path.exists(os.path.join(REPO_ROOT, source_ref)):
        return f"Rejected: source_ref not found -> {source_ref} (ingest it first)"
    claims, _ = core.load_claims(REPO_ROOT)
    cid = _append_claim(topic, dict(
        id=_next_id(claims), statement=statement, type=type, source_ref=source_ref,
        source_quote=source_quote, confidence=confidence,
        valid_from=valid_from, valid_until=valid_until, status="active"))
    return f"Added {cid} to 30-ledger/claims/{topic}.md. Run ledger_audit to confirm integrity."


@mcp.tool()
def ledger_supersede(
    old_id: str,
    new_statement: str,
    source_ref: str,
    changed_on: str,
    source_quote: str = "",
    confidence: str = "high",
) -> str:
    """Record that a fact changed: retire old_id and add the new truth.

    This is the ledger's core move — facts are never overwritten. The old claim
    is closed (status superseded, valid_until=changed_on) and a new active claim
    is created (valid_from=changed_on) linked back to it. `changed_on` is the
    YYYY-MM-DD the change took effect. Past as-of queries still see the old fact.
    """
    if not core._is_date(changed_on):
        return "Rejected: changed_on must be YYYY-MM-DD"
    if source_ref != "model-prior" and not os.path.exists(os.path.join(REPO_ROOT, source_ref)):
        return f"Rejected: source_ref not found -> {source_ref}"
    claims, _ = core.load_claims(REPO_ROOT)
    old = next((c for c in claims if c.get("id") == old_id), None)
    if not old:
        return f"Rejected: no claim '{old_id}'"
    topic = old.get("topic")
    new_id = _next_id(claims)
    _append_claim(topic, dict(
        id=new_id, statement=new_statement, type=old.get("type", "claim"),
        source_ref=source_ref, source_quote=source_quote, confidence=confidence,
        valid_from=changed_on, valid_until="", status="active", supersedes=old_id))
    core.update_claim_fields(REPO_ROOT, old_id, {
        "status": "superseded", "valid_until": changed_on,
        "superseded_by": new_id, "updated": str(date.today())})
    return (f"Superseded {old_id} -> {new_id} as of {changed_on}. "
            f"Old fact preserved for as-of queries. Run ledger_audit.")


@mcp.tool()
def ledger_contest(id_a: str, id_b: str, note: str = "") -> str:
    """Mark two claims as contested (sources genuinely disagree).

    Neither is deleted. Both get status=contested and reference each other in
    `contradicts`, so topic views and audits surface the dispute for a human.
    """
    claims, _ = core.load_claims(REPO_ROOT)
    ids = {c.get("id") for c in claims}
    for cid in (id_a, id_b):
        if cid not in ids:
            return f"Rejected: no claim '{cid}'"
    note_val = f'"{note}"' if note else "null"
    core.update_claim_fields(REPO_ROOT, id_a, {
        "status": "contested", "contradicts": f"[{id_b}]", "note": note_val,
        "updated": str(date.today())})
    core.update_claim_fields(REPO_ROOT, id_b, {
        "status": "contested", "contradicts": f"[{id_a}]", "note": note_val,
        "updated": str(date.today())})
    return f"Marked {id_a} and {id_b} as contested. Run ledger_audit."


@mcp.tool()
def ledger_audit() -> str:
    """Run full validation: schema, provenance, temporal & supersession integrity."""
    issues, claims = core.validate(REPO_ROOT)
    errors = [m for s, m in issues if s == "ERROR"]
    warns = [m for s, m in issues if s == "WARN"]
    if not issues:
        return f"OK — {len(claims)} claims, 0 errors, 0 warnings."
    lines = [f"{s}: {m}" for s, m in issues]
    return (f"{len(errors)} error(s), {len(warns)} warning(s) across {len(claims)} claims:\n"
            + "\n".join(lines))


if __name__ == "__main__":
    mcp.run()
