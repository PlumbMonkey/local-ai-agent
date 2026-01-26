"""Browser MCP Server for web research capabilities.

Provides tools for:
- Quick search (StackOverflow, docs, GitHub)
- Page scraping and content extraction
- Documentation fetching
- Error lookup
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus, urljoin, urlparse

logger = logging.getLogger(__name__)

# Try to import web libraries
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    logger.warning("aiohttp not installed - browser features limited")

try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False
    logger.warning("beautifulsoup4 not installed - browser features limited")


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SearchResult:
    """A single search result."""

    title: str
    url: str
    snippet: str
    source: str  # stackoverflow, github, docs, etc.


@dataclass
class PageContent:
    """Scraped page content."""

    url: str
    title: str
    content: str
    code_blocks: List[str]
    links: List[Dict[str, str]]


@dataclass
class ToolDefinition:
    """MCP tool definition."""

    name: str
    description: str
    input_schema: Dict[str, Any]


# ═══════════════════════════════════════════════════════════════════════════════
# Browser MCP Server
# ═══════════════════════════════════════════════════════════════════════════════


class BrowserMCPServer:
    """
    MCP Server for browser/web research capabilities.

    Provides tools for searching documentation, scraping pages,
    and finding error solutions.
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_content_length: int = 50000,
        user_agent: Optional[str] = None,
    ):
        """
        Initialize browser server.

        Args:
            timeout: Request timeout in seconds
            max_content_length: Max characters to return from page
            user_agent: Optional custom user agent
        """
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 LocalAIAgent/1.0"
        )
        self._session: Optional[Any] = None

    @property
    def tools(self) -> List[ToolDefinition]:
        """Get list of available tools."""
        return [
            ToolDefinition(
                name="browser.quick_search",
                description=(
                    "Search for programming help on StackOverflow, GitHub, "
                    "or documentation sites"
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query",
                        },
                        "source": {
                            "type": "string",
                            "enum": ["stackoverflow", "github", "docs", "all"],
                            "description": "Source to search",
                            "default": "all",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max results to return",
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
            ),
            ToolDefinition(
                name="browser.scrape_page",
                description="Scrape and extract content from a web page",
                input_schema={
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to scrape",
                        },
                        "extract_code": {
                            "type": "boolean",
                            "description": "Extract code blocks separately",
                            "default": True,
                        },
                    },
                    "required": ["url"],
                },
            ),
            ToolDefinition(
                name="browser.fetch_documentation",
                description="Fetch documentation for a library or API",
                input_schema={
                    "type": "object",
                    "properties": {
                        "library": {
                            "type": "string",
                            "description": "Library name (e.g., 'python:asyncio', 'npm:express')",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Specific topic or function to look up",
                        },
                    },
                    "required": ["library"],
                },
            ),
            ToolDefinition(
                name="browser.lookup_error",
                description="Look up an error message for solutions",
                input_schema={
                    "type": "object",
                    "properties": {
                        "error": {
                            "type": "string",
                            "description": "Error message to look up",
                        },
                        "language": {
                            "type": "string",
                            "description": "Programming language",
                            "default": "python",
                        },
                    },
                    "required": ["error"],
                },
            ),
        ]

    async def handle_call(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle a tool call."""
        handlers = {
            "browser.quick_search": self._quick_search,
            "browser.scrape_page": self._scrape_page,
            "browser.fetch_documentation": self._fetch_documentation,
            "browser.lookup_error": self._lookup_error,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            return await handler(**arguments)
        except Exception as e:
            logger.error(f"Error in {tool_name}: {e}")
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════════════════
    # Tool Implementations
    # ═══════════════════════════════════════════════════════════════════════════

    async def _quick_search(
        self,
        query: str,
        source: str = "all",
        limit: int = 5,
    ) -> Dict[str, Any]:
        """Search for programming help."""
        if not AIOHTTP_AVAILABLE:
            return {"error": "aiohttp not installed"}

        results = []

        if source in ["stackoverflow", "all"]:
            so_results = await self._search_stackoverflow(query, limit)
            results.extend(so_results)

        if source in ["github", "all"]:
            gh_results = await self._search_github(query, limit)
            results.extend(gh_results)

        if source in ["docs", "all"]:
            doc_results = await self._search_docs(query, limit)
            results.extend(doc_results)

        # Dedupe and limit
        seen_urls = set()
        unique_results = []
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique_results.append(r)
                if len(unique_results) >= limit:
                    break

        return {
            "query": query,
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "snippet": r.snippet,
                    "source": r.source,
                }
                for r in unique_results
            ],
            "count": len(unique_results),
        }

    async def _scrape_page(
        self,
        url: str,
        extract_code: bool = True,
    ) -> Dict[str, Any]:
        """Scrape content from a web page."""
        if not AIOHTTP_AVAILABLE or not BS4_AVAILABLE:
            return {"error": "Required libraries not installed (aiohttp, beautifulsoup4)"}

        try:
            content = await self._fetch_url(url)
            if not content:
                return {"error": "Failed to fetch page"}

            soup = BeautifulSoup(content, "lxml")

            # Remove script and style elements
            for elem in soup(["script", "style", "nav", "footer", "header"]):
                elem.decompose()

            # Get title
            title = soup.title.string if soup.title else ""

            # Extract code blocks
            code_blocks = []
            if extract_code:
                for code in soup.find_all(["code", "pre"]):
                    code_text = code.get_text().strip()
                    if code_text and len(code_text) > 10:
                        code_blocks.append(code_text)

            # Get main content
            main_content = soup.get_text(separator="\n")
            # Clean up whitespace
            main_content = re.sub(r"\n\s*\n", "\n\n", main_content)
            main_content = main_content.strip()

            # Truncate if needed
            if len(main_content) > self.max_content_length:
                main_content = main_content[: self.max_content_length] + "\n...[truncated]"

            # Get links
            links = []
            for a in soup.find_all("a", href=True)[:20]:
                href = a.get("href", "")
                if href.startswith("http"):
                    links.append({"text": a.get_text().strip()[:100], "url": href})

            return {
                "url": url,
                "title": title,
                "content": main_content,
                "code_blocks": code_blocks[:10],  # Limit code blocks
                "links": links,
            }

        except Exception as e:
            return {"error": f"Scrape failed: {str(e)}"}

    async def _fetch_documentation(
        self,
        library: str,
        topic: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch documentation for a library."""
        # Parse library format: "python:asyncio" or just "requests"
        if ":" in library:
            ecosystem, lib_name = library.split(":", 1)
        else:
            # Guess ecosystem
            ecosystem = "python"
            lib_name = library

        # Build doc URL based on ecosystem
        doc_urls = self._get_doc_urls(ecosystem, lib_name, topic)

        results = []
        for name, url in doc_urls.items():
            content = await self._fetch_url(url)
            if content:
                results.append({
                    "source": name,
                    "url": url,
                    "available": True,
                })
            else:
                results.append({
                    "source": name,
                    "url": url,
                    "available": False,
                })

        # Try to scrape first available doc
        for result in results:
            if result["available"]:
                scraped = await self._scrape_page(result["url"])
                if "error" not in scraped:
                    return {
                        "library": library,
                        "topic": topic,
                        "documentation": scraped,
                        "other_sources": results,
                    }

        return {
            "library": library,
            "topic": topic,
            "error": "Could not fetch documentation",
            "tried_sources": results,
        }

    async def _lookup_error(
        self,
        error: str,
        language: str = "python",
    ) -> Dict[str, Any]:
        """Look up an error message for solutions."""
        # Clean error for search
        clean_error = self._clean_error_for_search(error)

        # Search StackOverflow specifically for errors
        query = f"{language} {clean_error}"
        results = await self._search_stackoverflow(query, limit=5)

        if not results:
            # Try broader search
            results = await self._quick_search(query, source="all", limit=5)
            return results

        # Try to get top answer
        top_result = results[0] if results else None
        answer = None

        if top_result:
            scraped = await self._scrape_page(top_result.url)
            if "error" not in scraped:
                answer = {
                    "title": top_result.title,
                    "url": top_result.url,
                    "content": scraped.get("content", "")[:5000],
                    "code_examples": scraped.get("code_blocks", [])[:3],
                }

        return {
            "error": error,
            "language": language,
            "top_answer": answer,
            "related_results": [
                {"title": r.title, "url": r.url, "snippet": r.snippet}
                for r in results[1:5]
            ],
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════════════

    async def _get_session(self):
        """Get or create aiohttp session."""
        if not AIOHTTP_AVAILABLE:
            return None

        if self._session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers={"User-Agent": self.user_agent},
            )
        return self._session

    async def _fetch_url(self, url: str) -> Optional[str]:
        """Fetch URL content."""
        session = await self._get_session()
        if not session:
            return None

        try:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status} for {url}")
                    return None
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return None

    async def _search_stackoverflow(
        self, query: str, limit: int = 5
    ) -> List[SearchResult]:
        """Search StackOverflow via their API."""
        session = await self._get_session()
        if not session:
            return []

        # Use StackOverflow search API
        api_url = (
            f"https://api.stackexchange.com/2.3/search/advanced"
            f"?order=desc&sort=relevance&q={quote_plus(query)}"
            f"&site=stackoverflow&pagesize={limit}"
        )

        try:
            async with session.get(api_url) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get("items", [])[:limit]:
                        results.append(
                            SearchResult(
                                title=item.get("title", ""),
                                url=item.get("link", ""),
                                snippet=", ".join(item.get("tags", [])),
                                source="stackoverflow",
                            )
                        )
                    return results
        except Exception as e:
            logger.error(f"StackOverflow search failed: {e}")

        return []

    async def _search_github(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search GitHub for code/repos."""
        session = await self._get_session()
        if not session:
            return []

        # Use GitHub code search (limited without auth)
        api_url = (
            f"https://api.github.com/search/repositories"
            f"?q={quote_plus(query)}&per_page={limit}"
        )

        try:
            async with session.get(
                api_url, headers={"Accept": "application/vnd.github.v3+json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    results = []
                    for item in data.get("items", [])[:limit]:
                        results.append(
                            SearchResult(
                                title=item.get("full_name", ""),
                                url=item.get("html_url", ""),
                                snippet=item.get("description", "") or "",
                                source="github",
                            )
                        )
                    return results
        except Exception as e:
            logger.error(f"GitHub search failed: {e}")

        return []

    async def _search_docs(self, query: str, limit: int = 5) -> List[SearchResult]:
        """Search documentation sites."""
        # Build DuckDuckGo search for docs
        # Note: In production, you'd want to use proper search APIs
        results = []

        # Try Python docs specifically for Python queries
        if any(kw in query.lower() for kw in ["python", "async", "import", "class"]):
            results.append(
                SearchResult(
                    title=f"Python Docs: {query}",
                    url=f"https://docs.python.org/3/search.html?q={quote_plus(query)}",
                    snippet="Official Python documentation",
                    source="docs",
                )
            )

        # DevDocs search
        results.append(
            SearchResult(
                title=f"DevDocs: {query}",
                url=f"https://devdocs.io/#q={quote_plus(query)}",
                snippet="DevDocs - API documentation browser",
                source="docs",
            )
        )

        return results[:limit]

    def _get_doc_urls(
        self, ecosystem: str, lib_name: str, topic: Optional[str]
    ) -> Dict[str, str]:
        """Get documentation URLs for a library."""
        urls = {}

        if ecosystem == "python":
            # Standard library
            std_libs = {
                "asyncio", "os", "sys", "json", "typing", "pathlib",
                "collections", "itertools", "functools", "dataclasses",
            }
            if lib_name in std_libs:
                base = f"https://docs.python.org/3/library/{lib_name}.html"
                urls["python_docs"] = base
            else:
                # Third-party
                urls["pypi"] = f"https://pypi.org/project/{lib_name}/"
                urls["readthedocs"] = f"https://{lib_name}.readthedocs.io/"

        elif ecosystem == "npm":
            urls["npm"] = f"https://www.npmjs.com/package/{lib_name}"

        elif ecosystem == "rust":
            urls["docs_rs"] = f"https://docs.rs/{lib_name}"
            urls["crates"] = f"https://crates.io/crates/{lib_name}"

        # Add topic if specified
        if topic:
            for name, url in list(urls.items()):
                if "#" not in url:
                    urls[name] = f"{url}#{topic}"

        return urls

    def _clean_error_for_search(self, error: str) -> str:
        """Clean error message for better search results."""
        # Remove file paths
        error = re.sub(r'File "[^"]+",?', "", error)
        # Remove line numbers
        error = re.sub(r"line \d+", "", error)
        # Remove memory addresses
        error = re.sub(r"0x[0-9a-fA-F]+", "", error)
        # Remove specific variable names that look like temp vars
        error = re.sub(r"\b_[a-z0-9_]+\b", "", error)
        # Clean up whitespace
        error = " ".join(error.split())
        # Truncate
        return error[:200]

    async def close(self):
        """Close the session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# ═══════════════════════════════════════════════════════════════════════════════
# MCP Protocol Integration
# ═══════════════════════════════════════════════════════════════════════════════


def create_browser_server() -> BrowserMCPServer:
    """Create a browser MCP server instance."""
    return BrowserMCPServer()


async def register_browser_tools(registry: Any) -> None:
    """Register browser tools with MCP registry."""
    server = create_browser_server()

    # Register each tool
    for tool in server.tools:
        # This would integrate with the actual MCP registry
        logger.info(f"Registered browser tool: {tool.name}")
