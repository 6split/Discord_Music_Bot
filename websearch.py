"""
Web search and scraping module using crawl4ai.
"""
from typing import List, Optional, Callable
import time
import json
import asyncio
import re
from urllib.parse import urlparse, parse_qs

from pydantic import BaseModel, Field
from crawl4ai import (
    AsyncWebCrawler, AdaptiveCrawler, AdaptiveConfig,
    BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig,
    LLMExtractionStrategy
)

from message_history import save_message_history

try:
    import requests
except ImportError:
    requests = None

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    webdriver = None
    Options = None
    Service = None
    WebDriverWait = None
    EC = None


# ==================== Configuration Constants ====================
class Config:
    """Centralized configuration constants."""
    MAX_ITERATIONS = 20
    DEFAULT_LLM_PROVIDER = "ollama/qwen3:8b"
    EMBEDDING_LLM_PROVIDER = "ollama/qwen3-embedding:4b"
    CHUNK_TOKEN_THRESHOLD = 2048
    CHUNK_OVERLAP_RATE = 0.01
    EXTRA_ARGS = {"temperature": 0.0, "max_tokens": 5000}
    MIN_CONTENT_LENGTH = 100
    MIN_ITERATIONS_FOR_TIMEOUT = 3
    ADAPTIVE_CONFIDENCE_THRESHOLD = 0.8
    ADAPTIVE_MAX_DEPTH = 3
    ADAPTIVE_BASE_MAX_PAGES = 10
    ADAPTIVE_BASE_TOP_K_LINKS = 3
    ADAPTIVE_MIN_GAIN_THRESHOLD = 0.01
    RELEVANCE_SCORE_THRESHOLD = 0.8
    RELEVANCE_SCORE_DECAY = 0.06
    PAGE_URL_COUNT_THRESHOLD = 10
    RESULT_LENGTH_THRESHOLD = 100
    RESULTS_TO_KEEP = 3


# ==================== Type Hints ====================
CallbackType = Optional[Callable[[str], None]]


# ==================== Models ====================
class Info(BaseModel):
    """Information extracted from a web page."""
    summary: str
    relevant: bool


class Article(BaseModel):
    """An article or search result item."""
    title: str
    link: str


class SearchResults(BaseModel):
    """Container for search results."""
    articles: List[Article]


# ==================== Helper Functions ====================
def _get_adaptive_config(iteration: int, state_path: str = "crawl.json") -> AdaptiveConfig:
    """Create an AdaptiveCrawler configuration for the given iteration."""
    return AdaptiveConfig(
        confidence_threshold=Config.ADAPTIVE_CONFIDENCE_THRESHOLD,
        max_depth=Config.ADAPTIVE_MAX_DEPTH,
        max_pages=Config.ADAPTIVE_BASE_MAX_PAGES + iteration * 100,
        top_k_links=Config.ADAPTIVE_BASE_TOP_K_LINKS + iteration * 20,
        min_gain_threshold=Config.ADAPTIVE_MIN_GAIN_THRESHOLD,
        save_state=True,
        state_path=state_path,
    )


def _get_llm_extraction_strategy(
    prompt: str,
    schema: dict,
    provider: str = Config.DEFAULT_LLM_PROVIDER,
    chunk_token_threshold: int = Config.CHUNK_TOKEN_THRESHOLD,
    overlap_rate: float = Config.CHUNK_OVERLAP_RATE,
    extra_args: Optional[dict] = None,
    verbose: bool = True,
) -> LLMExtractionStrategy:
    """Create an LLM extraction strategy with the given parameters."""
    final_extra_args = {**Config.EXTRA_ARGS, **(extra_args or {})}
    return LLMExtractionStrategy(
        llm_config=LLMConfig(provider=provider),
        schema=schema,
        extraction_type="schema",
        instruction=prompt,
        chunk_token_threshold=chunk_token_threshold,
        overlap_rate=overlap_rate,
        apply_chunking=True,
        input_format="markdown",
        extra_args=final_extra_args,
        verbose=verbose,
    )


def _get_search_extraction_strategy() -> LLMExtractionStrategy:
    """Create a search results extraction strategy for Google."""
    return LLMExtractionStrategy(
        llm_config=LLMConfig(provider=Config.DEFAULT_LLM_PROVIDER),
        schema=SearchResults.model_json_schema(),
        extraction_type="schema",
        instruction="""Extract the search results from the page.

Return:
{
    "articles": [
        {
            "title": "...",
            "link": "..."
        }
    ]
}

Only include actual search results.
CRITICAL RULES:
    - You MUST ONLY use URLs that are explicitly present in the page content.
    - NEVER fabricate, guess, or complete URLs.
    - If a URL is relative (e.g. /url?q=...), extract the full value from it.
    - If no valid URL exists for an item, DO NOT include it.
Ignore ads, navigation links, related searches, images, and page controls.

Return valid JSON only.
""",
        input_format="html",
        apply_chunking=True,
        chunk_token_threshold=Config.CHUNK_TOKEN_THRESHOLD,
        overlap_rate=Config.CHUNK_OVERLAP_RATE,
        verbose=True,
    )


# ==================== Core Functions ====================
def _find_google_url(html: str) -> Optional[str]:
    """Extract the actual Google search results page URL from the HTML."""
    # Look for base action that sets the search results path
    # Google uses something like: <form action="/search" method="GET">
    # and the results are at /search?q=...
    match = re.search(r'action=["\'](/search)["\']', html)
    if match:
        return "https://www.google.com" + match.group(1)
    return None


def _parse_google_search_results(html: str) -> List[dict]:
    """
    Parse Google search results from HTML using BeautifulSoup.

    Google uses div with class 'kb0PBd' as result containers, grouped under a
    parent div with 'N54PNb BToiNc' classes. The title is in an h3 tag inside
    the parent div, before the kb0PBd container.

    Returns a list of dicts with 'title', 'link', and 'description' keys.
    """
    import re

    results = []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except ImportError:
        return results

    # Strategy: Find all divs with class 'kb0PBd' (Google result containers)
    # Each group of kb0PBd containers is wrapped in a parent div with N54PNb BToiNc
    # The title is in an h3 tag within the parent div, before each kb0PBd container
    kb0pbd_containers = soup.find_all("div", class_="kb0PBd")

    print(f"DEBUG: Found {len(kb0pbd_containers)} kb0PBd result containers")

    # Group kb0PBd containers by their parent div (N54PNb BToiNc)
    # Each parent div contains one title (h3) and multiple kb0PBd containers
    kb0pbd_by_parent = {}
    for container in kb0pbd_containers:
        parent = container.parent
        if parent:
            # Convert class list to tuple for hashing (BeautifulSoup returns a list-like object)
            parent_key = (parent.name, tuple(parent.get('class', [])))
            if parent_key not in kb0pbd_by_parent:
                kb0pbd_by_parent[parent_key] = {
                    'title': '',
                    'containers': [],
                    'link_prefix': ''
                }
            kb0pbd_by_parent[parent_key]['containers'].append(container)

    print(f"DEBUG: Found {len(kb0pbd_by_parent)} groups of kb0PBd containers")

    for parent_key, data in kb0pbd_by_parent.items():
        parent = soup.select_one(f'[{parent_key[0]}][class*="{parent_key[1][0]}"]')
        if not parent:
            continue

        # Get the title from h3 inside the parent div
        title_tag = parent.find("h3")
        title = title_tag.get_text(strip=True) if title_tag else ""
        data['title'] = title

        # Clean up title - remove excessive whitespace and normalize
        title = " ".join(title.split())

        # Process each kb0PBd container in this group
        for container in data['containers']:
            # Find the anchor tag inside this container
            anchors = container.find_all("a", href=True)
            if not anchors:
                continue

            anchor = anchors[0]  # Take the first anchor (should be the result link)
            link = anchor["href"]

            # Skip Google's own pages (internal navigation)
            parsed_url = urlparse(link)
            if "google.com" in parsed_url.netloc or not parsed_url.path:
                continue

            # Clean up description - remove excessive whitespace
            description = " ".join(description.split())

            if title and len(title) > 2:
                results.append({
                    "title": title,
                    "link": link,
                    "description": description
                })

    print(f"DEBUG: Parsed {len(results)} results")
    return results


def _get_google_search_results(query: str, max_results: int = 10) -> List[dict]:
    """
    Get Google search results using selenium to fully render the page.

    Args:
        query: The search query string
        max_results: Maximum number of results to extract

    Returns:
        List of dicts with 'title', 'link', and 'description' keys
    """
    if webdriver is None:
        raise ImportError(
            "selenium is not installed. Install it with: pip install selenium webdriver-manager"
        )

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        raise ImportError("BeautifulSoup is required but not installed.")

    query = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}"

    chrome_options = Options()
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)

    try:
        # Navigate to Google and trigger the search
        driver.get(url)

        # Wait for the CAPTCHA page to appear (it should redirect quickly)
        wait = WebDriverWait(driver, 15)

        # Wait for search results to load - look for result items
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'div[jsname="L8p2Hb"] a[href]')))
        except Exception:
            pass

        html = driver.page_source

        # Debug: Check what we found
        soup = BeautifulSoup(html, "html.parser")
        h3_tags = soup.find_all("h3")
        anchor_tags = soup.find_all("a", href=True)
        print(f"DEBUG: Found {len(h3_tags)} h3 tags and {len(anchor_tags)} anchor tags")

        if len(h3_tags) > 0:
            print(f"DEBUG: First h3 tag text: {repr(str(h3_tags[0]))[:200]}")

        results = _parse_google_search_results(html)

        # Sort by relevance (Google puts most relevant at top)
        return sorted(results, key=lambda x: x.get("title", "").lower())[:max_results]

    finally:
        driver.quit()


def google_search(query: str) -> dict:
    """
    Perform a Google search using crawl4ai or selenium (fallback).

    Args:
        query: The search query string

    Returns:
        dict: Extracted search results with 'articles' key containing list of dicts
             with 'title', 'link', and 'description' keys
    """
    # Try selenium first (new implementation)
    try:
        results = _get_google_search_results(query)
        return {"articles": results}
    except Exception as e:
        print(f"Selenium search failed: {e}")
        # Fallback to crawl4ai
        try:
            query = query.replace(" ", "+")
            url = f"https://www.google.com/search?q={query}"

            browser_cfg = BrowserConfig(headless=False)

            extraction_strategy = _get_search_extraction_strategy()

            config = CrawlerRunConfig(
                extraction_strategy=extraction_strategy,
                stream=True,
            )

            async def crawl4ai_fallback():
                async with AsyncWebCrawler(config=browser_cfg) as crawler:
                    results = []
                    async for result in await crawler.arun(url=url, config=config):
                        results.append(result)
                return results[0].extracted_content if results else {"articles": []}

            import asyncio
            # Reduce timeout significantly for fallback to avoid hanging
            original_timeout = asyncio.get_event_loop().get_debug()
            try:
                # Set a short timeout for the fallback
                from concurrent.futures import TimeoutError
                result = asyncio.run(asyncio.wait_for(crawl4ai_fallback(), timeout=15))
            except asyncio.TimeoutError:
                print("Crawl4ai fallback timed out after 15 seconds")
                raise

            import asyncio
            result = asyncio.run(crawl4ai_fallback())
            return result
        except Exception as fallback_error:
            print(f"Crawl4ai fallback also failed: {fallback_error}")
            return {"articles": []}


def search_google(query: str) -> dict:
    """Synchronous wrapper around google_search."""
    return google_search(query)


def AI_websearch(query: str) -> dict:
    """
    Wrapper that runs the async google_search function.

    Args:
        query: The search query string

    Returns:
        dict: Extracted search results
    """
    return asyncio.run(google_search(query))


async def crawl_for_info(
    website: str,
    query: str,
    need_more_links: bool = False,
    callback: Optional[CallbackType] = None,
    estimated_time_left: float = 0.0,
) -> list:
    """
    Crawl a website to extract relevant information using adaptive crawling.

    Args:
        website: Starting URL for the crawl
        query: Search query to use during adaptive crawling
        need_more_links: If True, continues crawling until more links are found
        callback: Optional callback function called with status updates
        estimated_time_left: Estimated time remaining in seconds

    Returns:
        list: List of extracted content strings
    """
    start_time = time.time()
    iterations = 0
    potential_links = []
    page_urls: List[str] = []

    # Adaptive crawling loop
    while need_more_links and iterations < Config.MAX_ITERATIONS:
        max_pages = Config.ADAPTIVE_BASE_MAX_PAGES + iterations * 100
        top_k_links = Config.ADAPTIVE_BASE_TOP_K_LINKS + iterations * 20

        # Create adaptive config
        config = _get_adaptive_config(iterations)

        iterations += 1
        adaptive = AdaptiveCrawler(None, config)

        # Determine whether to resume or start fresh
        if iterations > 1:
            result = await adaptive.digest(
                start_url=potential_links[0].href if potential_links else website,
                query=query,
                resume_from="crawl.json",
            )
        else:
            result = await adaptive.digest(
                start_url=website,
                query=query,
            )

        # Print statistics
        adaptive.print_stats()
        potential_links = adaptive.state.pending_links
        print(f"{len(potential_links)} potential links found")

        # Get relevant content from knowledge base
        page_urls = []
        adaptive.export_knowledge_base("currentwebsearch.json")
        relevant_pages = adaptive.get_relevant_content(top_k=50)

        threshold = Config.RELEVANCE_SCORE_THRESHOLD - (Config.RELEVANCE_SCORE_DECAY * iterations)

        for page in relevant_pages:
            if page["score"] > threshold:
                print(f"- {page['url']} (score: {page['score']:.2f})")
                page_urls.append(page["url"])

        link_count = len(page_urls)
        if link_count >= Config.PAGE_URL_COUNT_THRESHOLD:
            need_more_links = False
            break

    # Extract information from collected pages
    data_list: list[str] = []
    count = 0

    for page_url in page_urls:
        count += 1

        # Callback with progress update
        if callback:
            status = f"Website scrape progress: {count}/{len(page_urls)}"
            if estimated_time_left > 1:
                status += f" Estimated Time Left: {estimated_time_left}"
            callback(f"Looking at Website: {page_url}. Source: {website}. {status}")

        # Create extraction strategy for this page
        prompt = f"""You are given a website as part of a larger web scraping taskforce to find relevant information.
Query: "{query}"

The summary field should include all important details.
Exclude titles, navigation elements, sidebars, and footer content.
If the page has no content related to the query, set relevant to False.
"""
        schema = Info.model_json_schema()
        llm_strategy = _get_llm_extraction_strategy(
            prompt=prompt,
            schema=schema,
        )

        # Crawl configuration
        crawl_config = CrawlerRunConfig(
            extraction_strategy=llm_strategy,
            cache_mode=CacheMode.BYPASS,
            fetch_ssl_certificate=True,
            wait_for_images=True,
        )

        async with AsyncWebCrawler(config=BrowserConfig(headless=False)) as crawler:
            result = await crawler.arun(url=page_url, config=crawl_config)

            if result.success:
                data = json.loads(result.extracted_content)

                # Filter for relevant content
                for item in data:
                    try:
                        # Handle both 'relevant' and 'relevannt' keys
                        relevant = item.get("relevant", False)
                        if not isinstance(relevant, bool):
                            relevant = item.get("relevannt", False)

                        if relevant:
                            summary = item.get("summary", "")
                            if summary.strip() != query:
                                data_list.append(summary)
                    except Exception:
                        continue

                # Deduplicate and convert back to list
                data_list = list(set(data_list))

                # Check if we have enough content
                result_len = sum(len(s) for s in data_list)
                if result_len > Config.RESULT_LENGTH_THRESHOLD and count >= 3:
                    break
            else:
                print(f"Error crawling {page_url}: {result.error_message}")

    elapsed = time.time() - start_time
    print(f"Extracted {len(data_list)} items in {elapsed:.2f} seconds")
    return data_list


def scrape_url(
    website: str,
    query: str,
    callback: Optional[CallbackType] = None,
    need_more_links: bool = False,
    estimated_time: float = 0.0,
) -> list:
    """
    Scrape a URL with automatic fallback if the first attempt yields no results.

    Args:
        website: Starting URL to scrape
        query: Search query to use
        callback: Optional callback function for progress updates
        need_more_links: If True, continue crawling until more links are found
        estimated_time: Estimated time remaining in seconds

    Returns:
        list: Extracted content strings

    Note:
        If the initial scrape returns less than 100 characters total,
        it automatically retries with additional link discovery.
    """
    result = asyncio.run(
        crawl_for_info(
            website=website,
            query=query,
            callback=callback,
            need_more_links=need_more_links,
            estimated_time_left=estimated_time,
        )
    )

    # Check if we got meaningful results
    result_len = sum(len(d) for d in result)
    print(f"Scrape result length: {result_len} characters")

    if result_len < Config.MIN_CONTENT_LENGTH:
        print("Initial scrape yielded minimal content, retrying with link discovery...")
        result = asyncio.run(
            crawl_for_info(
                website=website,
                query=query,
                callback=callback,
                need_more_links=True,
                estimated_time_left=estimated_time,
            )
        )

    return result


# ==================== Main Entry Point ====================
if __name__ == "__main__":
    import sys

    # Test the new selenium-based google_search function
    try:
        query = sys.argv[1] if len(sys.argv) > 1 else "Python tutorials"
        print(f"Testing google_search with query: '{query}'")
        print("-" * 50)

        results = google_search(query)

        print(json.dumps(results, indent=2))

        if results.get("articles"):
            print("\n--- Summary ---")
            for article in results["articles"][:3]:
                print(f"\nTitle: {article['title']}")
                print(f"Link: {article['link']}")
                print(f"Description: {article['description'][:200]}...")

        print("-" * 50)
        print("Test completed successfully!")

    except ImportError as e:
        print(f"Error: selenium is required but not installed.")
        print(f"Install it with: pip install selenium webdriver-manager")
        print(f"Error details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during search: {e}")
        sys.exit(1)
