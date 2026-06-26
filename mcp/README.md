# LLM Ledger — MCP server

Use your verifiable, time-aware ledger from **any** MCP client (Claude Desktop,
Cursor, etc.), not just Claude Code. The client's LLM reasons; this server gives
it trustworthy primitives.

## Tools

| Tool | What it does |
| --- | --- |
| `ledger_search(query, as_of?)` | Find claims; `as_of=YYYY-MM-DD` time-travels to that date |
| `ledger_get_topic(topic)` | Return the assembled topic view with footnotes |
| `ledger_timeline(topic, as_of?)` | How knowledge changed over time / as-of snapshot |
| `ledger_list_topics()` | All topics + claim counts |
| `ledger_ingest(title, content, source_url?)` | Stash a raw source into `10-inbox` |
| `ledger_add_claim(...)` | Append a **validated** claim (rejects bad writes) |
| `ledger_audit()` | Full integrity check |

Reads carry source + confidence; writes are validated before they land. The
server can't invent facts — it only returns what's in the ledger.

## Setup

```bash
pip install -r mcp/requirements.txt
```

Register it with your client. Example (Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "llm-ledger": {
      "command": "python3",
      "args": ["/absolute/path/to/llm-ledger/mcp/server.py"],
      "env": { "LEDGER_ROOT": "/absolute/path/to/llm-ledger" }
    }
  }
}
```

`LEDGER_ROOT` points at your ledger folder. Restart the client and the tools appear.

## Note
This MCP server is an optional add-on. The core template stays dependency-free;
only this folder needs the `mcp` package.
