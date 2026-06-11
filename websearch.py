"""
Pretty bad code, beacause I copied from an old project. Should work for the meantime though.
"""
from crawl4ai import AsyncWebCrawler, AdaptiveCrawler, AdaptiveConfig
import os
import asyncio
import json
from pydantic import BaseModel, Field
from typing import List
from crawl4ai import BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig
from crawl4ai import LLMExtractionStrategy
import time
from message_history import save_message_history

def AI_websearch(query : str):
    result = asyncio.run(crawl_for_info(f"https://www.google.com/search?q={query}", query, True))
    return result



async def google_search(query: str):
    query = query.replace(" ", "+")
    url = f"https://www.google.com/search?q={query}"

    browser_cfg = BrowserConfig(headless=False)

    extraction_strategy = LLMExtractionStrategy(
        llm_config=LLMConfig(provider="ollama/qwen3:0.6b"),
        schema=SearchResults.model_json_schema(),
        extraction_type="schema",
        instruction="""
        Extract the search results from the page.

        Return:
        {
            "results": [
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
        chunk_token_threshold=2048,
        verbose=True,
    )

    config = CrawlerRunConfig(
        extraction_strategy=extraction_strategy,
        stream=True
    )

    async with AsyncWebCrawler(config=browser_cfg) as crawler:
        results = []
        async for result in await crawler.arun(url=url,config=config):
            results.append(result)

        return result.extracted_content


def search_google(query: str):
    return asyncio.run(google_search(query))

class Info(BaseModel):
    summary: str
    relevant: bool

class Article(BaseModel):
    title: str
    link: str

class SearchResults(BaseModel):
    articles: List[Article]

async def crawl_for_info(website : str, query : str, need_more_links=False, call_back=None, estimated_time_left=0):
    MAX_ITERATIONS = 20
    start_time = time.time()
    if not need_more_links:
        page_urls = [website]
        save_message_history("{}","crawl.json")
    else:
        page_urls = []
    iterations = 0
    searched_page_urls = []
    async with AsyncWebCrawler() as crawler:
        potential_links = []
        while need_more_links and iterations < MAX_ITERATIONS:
            max_pages = 10 + iterations * 100
            top_k_links = 3 + iterations * 20
            print(f"Finding more links: iteration {iterations}, max pages {max_pages}, top k links {top_k_links}")
        # if call_back:
        #     call_back(f"Scraping {website} for more information...")
            # Create an adaptive crawler (config is optional)
        
            config = AdaptiveConfig(
                confidence_threshold=0.8,    # Stop when 80% confident (default: 0.7)
                max_depth=3,
                max_pages=10 + iterations * 100,               # Maximum pages to crawl (default: 20)
                top_k_links=3 + iterations * 20,              # Links to follow per page (default: 3)
                min_gain_threshold=0.01,     # Minimum expected gain to continue (default: 0.1)
                save_state=True,
                state_path="crawl.json",
            )
            
            config = AdaptiveConfig(
                strategy="embedding",
                # Embedding model — used for text-to-vector calls
                embedding_llm_config=LLMConfig(
                    provider='ollama/qwen3-embedding:4b',
                ),
                # Query model — used for chat completion (query expansion)
                query_llm_config = LLMConfig(provider="ollama/qwen3:8b"),
                embedding_min_confidence_threshold=0.1,
            )

            iterations += 1
            adaptive = AdaptiveCrawler(crawler, config)

            # Start crawling with a query
            if iterations > 1:
                result = await adaptive.digest(
                    start_url=potential_links[0].href,
                    query=query,
                    resume_from="crawl.json"
                )
            else:
                result = await adaptive.digest(
                    start_url=website,
                    query=query,
                )
            # View statistics
            adaptive.print_stats()
            potential_links = adaptive.state.pending_links
            print(f"{len(potential_links)} num of potential links")

            # Get the most relevant content
            page_urls = []
            adaptive.export_knowledge_base("currentwebsearch.json")
            relevant_pages = adaptive.get_relevant_content(top_k=50)
            for page in relevant_pages:
                threshold = 0.8 - (0.6/MAX_ITERATIONS * iterations)
                if page['score'] > threshold:
                    print(f"- {page['url']} (score: {page['score']:.2f})")
                    page_urls.append(page['url'])
            
            link_count = len(page_urls)
            if link_count >= 10:
                need_more_links = False
                break

    data_list = []
    count = 0
    for page_url in page_urls:
            searched_page_urls.append(page_url)
            count += 1
            if call_back:
                if estimated_time_left > 1:
                    call_back(f"Looking at Website: {page_url}. Source: {website}. Website scrape progress: {(count)}/{len(page_urls)} Estimated Time Left: {estimated_time_left}")
                else:
                    call_back(f"Looking at Website: {page_url}. Source: {website}. Website scrape progress: {(count)}/{len(page_urls)}")
            
            prompt = f"You are given a website as part of a larger web scraping taskforce to find relevant information for an end user. Here is the query to answer: \"{query}\". The summary field should include: All important details. Summary should exclude: Titles, Navigation elements, Sidebars, Footer content. If there is not content related to the query, set the value of the relevant field to False"
            extraction_schema = Info.model_json_schema()
            browser_cfg = BrowserConfig(headless=False)
            llm_strategy = LLMExtractionStrategy(
                llm_config = LLMConfig(provider="ollama/qwen3:8b"),
                schema=extraction_schema,
                extraction_type="schema",
                instruction= prompt,
                chunk_token_threshold= 2000,
                overlap_rate=0.01,
                apply_chunking=True,
                input_format="markdown",   # or "html", "fit_markdown"
                extra_args={"temperature": 0.0, "max_tokens": 5000},
                verbose=True
            )
            # 2. Build the crawler config
            crawl_config = CrawlerRunConfig(
                extraction_strategy=llm_strategy,
                cache_mode=CacheMode.BYPASS,
                fetch_ssl_certificate=True,
                wait_for_images=True,
                # wait_for="networkidle",
            )
            async with AsyncWebCrawler(config=browser_cfg) as crawler1:
                # 4. Let's say we want to crawl a single page
                result = await crawler1.arun(
                    url=page_url,
                    config=crawl_config
                )

                if result.success:
                    # 5. The extracted content is presumably JSON
                    data = json.loads(result.extracted_content)
                    print("Extracted items:", data)

                    # 6. Show usage stats
                    llm_strategy.show_usage()  # prints token usage
                    for d in data:
                            try:
                                relevant = False
                                try:
                                    relevant = d['relevant']
                                except:
                                    relevant = d['relevannt']
                                if relevant:
                                    d = d['summary']
                                    if d.strip() != query:
                                        data_list.append(d)
                            except Exception as e:
                                print(f"Error with json format? {e}")
                    #Removes duplicates using a set
                    data_list = set(data_list)
                    data_list = list(data_list)

                    result_len = 0
                    for string in data_list:
                        result_len += len(string)
                    if result_len > 100 and count > 3:
                        break
                else:
                    print("Error:", result.error_message)

    print(f"Extracted Data: {data_list}")
    print(f"Time for web crawling/scriping was {time.time() - start_time: 0.2f} seconds")
    return data_list

def scrape_url(website : str, query: str, callback=None, need_more_links=False, estimated_time=0):
    """
    Docstring for scrape_url
    
    :param website: Description
    :type website: str
    :param query: Description
    :type query: str
    :param callback: Description
    :param need_more_links: Bool for if we need more links. Should always be false.
    :param estimated_time: Description
    """
    a = asyncio.run(crawl_for_info(website, query, call_back=callback, need_more_links=need_more_links, estimated_time_left=estimated_time))
    result_len = 0
    for d in a:
        result_len += len(d)
    print(f"Scrape result: {a}")
    if result_len < 100: #if we didn't get info from the actual site, try some other links
        a = asyncio.run(crawl_for_info(website, query, True, call_back=callback, estimated_time_left=estimated_time))
    return a

if __name__ == "__main__":
    url = "https://www.nytimes.com"
    prompt = "Current events Television"
    a = scrape_url(url, prompt)
    print("Finished_scrape")
    # print(search_google("Minecraft Update"))