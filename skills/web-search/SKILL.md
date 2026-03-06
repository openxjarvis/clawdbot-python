---
name: web-search
description: "Search the web for information and fetch URL content. Use when user asks to search for recent information, look up websites, fetch web page content, or find online resources. No external tools required — uses built-in web_search and web_fetch capabilities."
metadata: { "openclaw": { "emoji": "🔍", "always": true } }
---

# Web Search

Search the web for information and fetch content from URLs.

## Tools Available

- **web_search**: Search for information (if available)
- **web_fetch**: Fetch content from specific URLs

## Search Strategies

1. **Direct URL fetch**: If user provides a URL, use web_fetch directly
2. **Search query**: Use web_search to find relevant pages
3. **Multiple sources**: Fetch multiple URLs for comprehensive info

## Best Practices

- Verify information from multiple sources
- Cite sources in your response
- Summarize content clearly
- Extract key information relevant to the query

## Example Queries

- "Search for Python asyncio tutorial"
- "What's on the Python homepage?"
- "Find documentation for FastAPI"
- "Get the latest news about AI"
