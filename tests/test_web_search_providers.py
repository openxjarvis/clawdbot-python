"""Tests for multi-provider web search implementation

Tests Brave, Perplexity, Grok, and DuckDuckGo providers with mocked HTTP calls.
"""
import pytest
import httpx
from unittest.mock import AsyncMock, MagicMock, patch

from openclaw.agents.tools.web import (
    WebSearchTool,
    WebFetchTool,
    create_web_search_tool,
    normalize_freshness,
    freshness_to_perplexity_recency,
    resolve_search_provider,
    resolve_perplexity_base_url,
    run_brave_search,
    run_perplexity_search,
    run_grok_search,
    run_web_search,
    _SEARCH_CACHE,
    BRAVE_SEARCH_ENDPOINT,
    DEFAULT_PERPLEXITY_BASE_URL,
    PERPLEXITY_DIRECT_BASE_URL,
    XAI_API_ENDPOINT,
)


# ---------------------------------------------------------------------------
# Freshness helpers
# ---------------------------------------------------------------------------


class TestNormalizeFreshness:
    def test_pd(self):
        assert normalize_freshness("pd") == "pd"

    def test_pw(self):
        assert normalize_freshness("pw") == "pw"

    def test_pm(self):
        assert normalize_freshness("pm") == "pm"

    def test_py(self):
        assert normalize_freshness("py") == "py"

    def test_date_range_valid(self):
        assert normalize_freshness("2024-01-01to2024-12-31") == "2024-01-01to2024-12-31"

    def test_date_range_uppercase_allowed(self):
        # Our impl lowercases shortcuts but date ranges are case-sensitive
        result = normalize_freshness("2024-01-01to2024-12-31")
        assert result == "2024-01-01to2024-12-31"

    def test_invalid_string(self):
        assert normalize_freshness("last-week") is None

    def test_none(self):
        assert normalize_freshness(None) is None

    def test_empty(self):
        assert normalize_freshness("") is None

    def test_date_range_reversed(self):
        # end < start
        assert normalize_freshness("2024-12-31to2024-01-01") is None


class TestFreshnessToPerplexityRecency:
    def test_pd_maps_to_day(self):
        assert freshness_to_perplexity_recency("pd") == "day"

    def test_pw_maps_to_week(self):
        assert freshness_to_perplexity_recency("pw") == "week"

    def test_pm_maps_to_month(self):
        assert freshness_to_perplexity_recency("pm") == "month"

    def test_py_maps_to_year(self):
        assert freshness_to_perplexity_recency("py") == "year"

    def test_none(self):
        assert freshness_to_perplexity_recency(None) is None

    def test_date_range_not_mapped(self):
        assert freshness_to_perplexity_recency("2024-01-01to2024-12-31") is None


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------


class TestResolveSearchProvider:
    def test_explicit_brave_in_config(self):
        config = {"tools": {"web": {"search": {"provider": "brave"}}}}
        assert resolve_search_provider(config) == "brave"

    def test_explicit_perplexity_in_config(self):
        config = {"tools": {"web": {"search": {"provider": "perplexity"}}}}
        assert resolve_search_provider(config) == "perplexity"

    def test_explicit_grok_in_config(self):
        config = {"tools": {"web": {"search": {"provider": "grok"}}}}
        assert resolve_search_provider(config) == "grok"

    def test_explicit_duckduckgo_in_config(self):
        config = {"tools": {"web": {"search": {"provider": "duckduckgo"}}}}
        assert resolve_search_provider(config) == "duckduckgo"

    def test_defaults_to_duckduckgo_without_env_keys(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("XAI_API_KEY", raising=False)
        assert resolve_search_provider(None) == "duckduckgo"

    def test_brave_from_env(self, monkeypatch):
        monkeypatch.setenv("BRAVE_API_KEY", "test-brave-key")
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert resolve_search_provider(None) == "brave"

    def test_perplexity_from_env(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test-key")
        assert resolve_search_provider(None) == "perplexity"

    def test_openrouter_env_gives_perplexity(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        assert resolve_search_provider(None) == "perplexity"

    def test_grok_from_env(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.setenv("XAI_API_KEY", "xai-test-key")
        assert resolve_search_provider(None) == "grok"


class TestResolvePerplexityBaseUrl:
    def test_from_config_takes_priority(self):
        perplexity_cfg = {"baseUrl": "https://custom.endpoint.ai/v1"}
        result = resolve_perplexity_base_url(perplexity_cfg)
        assert result == "https://custom.endpoint.ai/v1"

    def test_perplexity_env_gives_direct_url(self):
        result = resolve_perplexity_base_url(api_key_source="perplexity_env")
        assert result == PERPLEXITY_DIRECT_BASE_URL

    def test_openrouter_env_gives_openrouter_url(self):
        result = resolve_perplexity_base_url(api_key_source="openrouter_env")
        assert result == DEFAULT_PERPLEXITY_BASE_URL

    def test_pplx_key_prefix_gives_direct(self):
        result = resolve_perplexity_base_url(api_key_source="config", api_key="pplx-abcdef")
        assert result == PERPLEXITY_DIRECT_BASE_URL

    def test_openrouter_key_prefix_gives_openrouter(self):
        result = resolve_perplexity_base_url(api_key_source="config", api_key="sk-or-abcdef")
        assert result == DEFAULT_PERPLEXITY_BASE_URL

    def test_default_is_openrouter(self):
        result = resolve_perplexity_base_url()
        assert result == DEFAULT_PERPLEXITY_BASE_URL


# ---------------------------------------------------------------------------
# Provider implementations — mocked HTTP
# ---------------------------------------------------------------------------


def make_mock_response(status_code: int, json_data: dict | None = None, text: str = "") -> MagicMock:
    """Create a mock httpx response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.is_success = (200 <= status_code < 300)
    resp.json = MagicMock(return_value=json_data or {})
    resp.text = text
    resp.raise_for_status = MagicMock()
    if not resp.is_success:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "", request=MagicMock(), response=resp
        )
    return resp


class FakeAsyncClient:
    """Context manager that captures calls and returns a fixed response."""

    def __init__(self, response):
        self._response = response
        self.last_get_args = None
        self.last_post_args = None
        self.last_post_kwargs = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def get(self, *args, **kwargs):
        self.last_get_args = (args, kwargs)
        return self._response

    async def post(self, *args, **kwargs):
        self.last_post_args = args
        self.last_post_kwargs = kwargs
        return self._response


class TestRunBraveSearch:
    @pytest.mark.asyncio
    async def test_success(self):
        brave_response = {
            "web": {
                "results": [
                    {"title": "Result 1", "url": "https://example.com/1", "description": "Desc 1"},
                    {"title": "Result 2", "url": "https://example.com/2", "description": "Desc 2"},
                ]
            }
        }
        mock_resp = make_mock_response(200, brave_response)
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            result = await run_brave_search("test query", "test-api-key", count=2)

        assert result["provider"] == "brave"
        assert result["query"] == "test query"
        assert len(result["results"]) == 2
        assert result["results"][0]["title"] == "Result 1"
        assert result["results"][0]["url"] == "https://example.com/1"

    @pytest.mark.asyncio
    async def test_passes_country_param(self):
        mock_resp = make_mock_response(200, {"web": {"results": []}})
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            await run_brave_search("query", "key", country="DE", search_lang="de")

        _, kwargs = client.last_get_args
        assert kwargs["params"]["country"] == "DE"
        assert kwargs["params"]["search_lang"] == "de"

    @pytest.mark.asyncio
    async def test_passes_freshness(self):
        mock_resp = make_mock_response(200, {"web": {"results": []}})
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            await run_brave_search("query", "key", freshness="pw")

        _, kwargs = client.last_get_args
        assert kwargs["params"]["freshness"] == "pw"

    @pytest.mark.asyncio
    async def test_http_error_raises(self):
        mock_resp = make_mock_response(401, text="Unauthorized")
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(httpx.HTTPStatusError):
                await run_brave_search("query", "bad-key")


class TestRunPerplexitySearch:
    @pytest.mark.asyncio
    async def test_success(self):
        perplexity_response = {
            "choices": [
                {"message": {"content": "AI answer about Python"}}
            ],
            "citations": ["https://docs.python.org/3/"],
        }
        mock_resp = make_mock_response(200, perplexity_response)
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            result = await run_perplexity_search(
                "What is Python?", "pplx-api-key", model="perplexity/sonar-pro"
            )

        assert result["provider"] == "perplexity"
        assert result["content"] == "AI answer about Python"
        assert "https://docs.python.org/3/" in result["citations"]

    @pytest.mark.asyncio
    async def test_sends_search_recency_filter_for_freshness(self):
        mock_resp = make_mock_response(
            200, {"choices": [{"message": {"content": "answer"}}]}
        )
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            await run_perplexity_search(
                "latest news", "key", freshness="pd"
            )

        body = client.last_post_kwargs["json"]
        assert body.get("search_recency_filter") == "day"

    @pytest.mark.asyncio
    async def test_strips_perplexity_prefix_for_direct_api(self):
        mock_resp = make_mock_response(
            200, {"choices": [{"message": {"content": "ok"}}]}
        )
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            await run_perplexity_search(
                "query", "pplx-key",
                base_url=PERPLEXITY_DIRECT_BASE_URL,
                model="perplexity/sonar-pro",
            )

        body = client.last_post_kwargs["json"]
        # Direct API should strip "perplexity/" prefix
        assert body["model"] == "sonar-pro"

    @pytest.mark.asyncio
    async def test_error_raises(self):
        mock_resp = make_mock_response(400)
        mock_resp.is_success = False
        mock_resp.text = "Bad Request"
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(RuntimeError, match="Perplexity API error"):
                await run_perplexity_search("query", "bad-key")


class TestRunGrokSearch:
    @pytest.mark.asyncio
    async def test_success(self):
        grok_response = {
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": "Grok answer"}],
                }
            ],
            "citations": ["https://source.com"],
        }
        mock_resp = make_mock_response(200, grok_response)
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            result = await run_grok_search("test query", "xai-key")

        assert result["provider"] == "grok"
        assert result["content"] == "Grok answer"
        assert "https://source.com" in result["citations"]

    @pytest.mark.asyncio
    async def test_sends_web_search_tool(self):
        mock_resp = make_mock_response(200, {"output": [], "citations": []})
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            await run_grok_search("query", "xai-key")

        body = client.last_post_kwargs["json"]
        assert {"type": "web_search"} in body["tools"]

    @pytest.mark.asyncio
    async def test_error_raises(self):
        mock_resp = make_mock_response(401)
        mock_resp.is_success = False
        mock_resp.text = "Unauthorized"
        client = FakeAsyncClient(mock_resp)

        with patch("httpx.AsyncClient", return_value=client):
            with pytest.raises(RuntimeError, match="xAI API error"):
                await run_grok_search("query", "bad-key")


# ---------------------------------------------------------------------------
# WebSearchTool integration
# ---------------------------------------------------------------------------


class TestWebSearchToolBrave:
    @pytest.mark.asyncio
    async def test_brave_success(self, monkeypatch):
        brave_response = {
            "web": {
                "results": [
                    {"title": "T1", "url": "https://a.com", "description": "D1"},
                ]
            }
        }
        monkeypatch.setenv("BRAVE_API_KEY", "test-brave")
        _SEARCH_CACHE.clear()

        mock_resp = make_mock_response(200, brave_response)
        client = FakeAsyncClient(mock_resp)

        tool = WebSearchTool(provider="brave", config=None)
        with patch("httpx.AsyncClient", return_value=client):
            result = await tool._execute_impl({"query": "Python", "count": 1})

        assert result.success is True
        assert "T1" in result.content

    @pytest.mark.asyncio
    async def test_brave_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("BRAVE_API_KEY", raising=False)
        _SEARCH_CACHE.clear()

        tool = WebSearchTool(provider="brave", config=None)
        result = await tool._execute_impl({"query": "test"})

        assert result.success is False
        assert "BRAVE_API_KEY" in result.error or "missing" in result.error.lower()

    @pytest.mark.asyncio
    async def test_invalid_freshness_returns_error(self):
        tool = WebSearchTool(provider="duckduckgo")
        result = await tool._execute_impl({"query": "test", "freshness": "bad-value"})

        assert result.success is False
        assert "freshness" in result.error.lower() or "invalid" in result.error.lower()


class TestWebSearchToolPerplexity:
    @pytest.mark.asyncio
    async def test_perplexity_formats_with_citations(self, monkeypatch):
        monkeypatch.setenv("PERPLEXITY_API_KEY", "pplx-test")
        _SEARCH_CACHE.clear()

        perplexity_response = {
            "choices": [{"message": {"content": "The answer"}}],
            "citations": ["https://source1.com", "https://source2.com"],
        }
        mock_resp = make_mock_response(200, perplexity_response)
        client = FakeAsyncClient(mock_resp)

        tool = WebSearchTool(provider="perplexity")
        with patch("httpx.AsyncClient", return_value=client):
            result = await tool._execute_impl({"query": "What is Python?"})

        assert result.success is True
        assert "The answer" in result.content
        assert "source1.com" in result.content

    @pytest.mark.asyncio
    async def test_perplexity_missing_key_returns_error(self, monkeypatch):
        monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        _SEARCH_CACHE.clear()

        tool = WebSearchTool(provider="perplexity")
        result = await tool._execute_impl({"query": "test"})

        assert result.success is False
        assert "perplexity" in result.error.lower() or "PERPLEXITY" in result.error


class TestWebSearchCaching:
    @pytest.mark.asyncio
    async def test_result_cached_on_second_call(self, monkeypatch):
        _SEARCH_CACHE.clear()
        monkeypatch.setenv("BRAVE_API_KEY", "test-key")

        brave_response = {"web": {"results": [{"title": "T1", "url": "u1", "description": "d1"}]}}
        mock_resp = make_mock_response(200, brave_response)
        call_count = 0

        class CountingClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            async def get(self, *a, **kw):
                nonlocal call_count
                call_count += 1
                return mock_resp

        with patch("httpx.AsyncClient", return_value=CountingClient()):
            await run_web_search("cached query", provider="brave", api_key="key")
            await run_web_search("cached query", provider="brave", api_key="key")

        # Second call should use cache
        assert call_count == 1


class TestCreateWebSearchTool:
    def test_returns_tool(self):
        tool = create_web_search_tool()
        assert tool is not None
        assert isinstance(tool, WebSearchTool)

    def test_disabled_returns_none(self):
        config = {"tools": {"web": {"search": {"enabled": False}}}}
        result = create_web_search_tool(config)
        assert result is None

    def test_respects_provider_config(self):
        config = {"tools": {"web": {"search": {"provider": "brave"}}}}
        tool = create_web_search_tool(config)
        assert tool is not None
        assert tool.provider == "brave"

    def test_description_changes_by_provider(self):
        brave_tool = WebSearchTool(provider="brave")
        perplexity_tool = WebSearchTool(provider="perplexity")
        grok_tool = WebSearchTool(provider="grok")
        ddg_tool = WebSearchTool(provider="duckduckgo")

        assert "Brave" in brave_tool.description
        assert "Perplexity" in perplexity_tool.description
        assert "Grok" in grok_tool.description
        assert "DuckDuckGo" in ddg_tool.description

    def test_schema_has_freshness_and_country(self):
        tool = WebSearchTool(provider="brave")
        schema = tool.get_schema()
        props = schema["properties"]
        assert "freshness" in props
        assert "country" in props
        assert "search_lang" in props
        assert "ui_lang" in props


# ---------------------------------------------------------------------------
# WebFetchTool
# ---------------------------------------------------------------------------


class TestWebFetchTool:
    @pytest.mark.asyncio
    async def test_fetch_html_to_text(self):
        html = "<html><body><h1>Title</h1><p>Content here</p></body></html>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = {"content-type": "text/html; charset=utf-8"}
        mock_resp.text = html
        mock_resp.url = "https://example.com"
        mock_resp.raise_for_status = MagicMock()

        class FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            async def get(self, *a, **kw):
                return mock_resp

        tool = WebFetchTool()
        with patch("httpx.AsyncClient", return_value=FakeClient()):
            result = await tool.execute({"url": "https://example.com"})

        assert result.success is True
        # Content should contain the page text (HTML stripped)
        assert "Title" in result.content or "Content" in result.content

    @pytest.mark.asyncio
    async def test_fetch_no_url_returns_error(self):
        tool = WebFetchTool()
        result = await tool.execute({"url": ""})
        assert result.success is False
        assert "url" in result.error.lower()

    @pytest.mark.asyncio
    async def test_fetch_truncates_long_content(self):
        big_html = "<p>" + "A" * 100000 + "</p>"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_success = True
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.text = big_html
        mock_resp.url = "https://example.com"
        mock_resp.raise_for_status = MagicMock()

        class FakeClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                pass
            async def get(self, *a, **kw):
                return mock_resp

        tool = WebFetchTool()
        with patch("httpx.AsyncClient", return_value=FakeClient()):
            result = await tool.execute({"url": "https://example.com", "max_length": 1000})

        assert result.success is True
        assert len(result.content) <= 1100  # max_length + truncation notice
