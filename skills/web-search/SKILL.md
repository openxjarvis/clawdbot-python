---
name: web-search
description: "Search the web and fetch URL content. Use when user asks to look up recent information, find documentation, fetch a web page, check a live site, or research a topic online. No external tools required — uses built-in web_search and web_fetch capabilities."
metadata: { "openclaw": { "emoji": "🔍", "always": true } }
---

# Web Search

Search the web for information and fetch content from URLs using built-in `web_search` and `web_fetch` tools.

## Decision Workflow

1. **User provides a URL** → use `web_fetch` directly
2. **User asks a question** → use `web_search` with a focused query, then `web_fetch` the most relevant results
3. **Need comprehensive info** → search, fetch multiple sources, cross-reference

## Tool Usage

### web_search

```
web_search query:"Python asyncio tutorial" max_results:5
```

Returns a list of URLs with titles and snippets. Refine the query if results are poor — try more specific terms, add the site name, or quote exact phrases.

### web_fetch

```
web_fetch url:"https://docs.python.org/3/library/asyncio.html"
```

Returns the page content as text. Use for:
- Fetching documentation pages
- Reading articles or blog posts
- Checking live site content

## Error Handling

- **No search results**: Rephrase the query with different keywords or broader terms. Try removing filters.
- **web_fetch fails or returns empty**: The site may block automated requests. Try an alternative source from the search results.
- **Content too large**: Extract only the relevant section. Summarize rather than dumping the full page.
- **Rate limits**: Space out requests. Prioritize the most relevant URLs rather than fetching everything.

## Guidelines

- Cite sources with URLs in responses so the user can verify.
- Summarize and extract key information rather than returning raw page content.
- Cross-reference multiple sources for factual claims.
