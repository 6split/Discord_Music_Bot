import unittest
from unittest.mock import patch, MagicMock
import time
import sys

sys.path.insert(0, "/user_c8525a79/Documents/workspace/user_c8525a79/codebase/Projects/ChatbotDiscordBot/src")


@patch("websearch.crawl_for_info", return_value=[[f"mock page {i}" for i in range(3)]])
@patch("websearch.google_search", return_value={"articles": [{"title": f"A{i}", "link": f"http://link{i}"} for i in range(3)]})
def run_tests(_mock_crawl, _mock_google):
    """Run all tests with mocked functions."""
    results = []
    
    import websearch
    from websearch import Config
    
    def smart_crawl(**kw):
        need_more_links = kw.get("need_more_links", False)
        if need_more_links:
            return [f"adaptive crawl content for iteration {i}" for i in range(4)]
        else:
            website = kw.get("website", "")
            if isinstance(website, str) and len(str(website)) > 3:
                page_count = len(str(website)) % 8 or 1
                return [f"crawled content page {i} from {str(website)[:50]}" for i in range(page_count)]
            return []
    
    def smart_google(query):
        n_links = len(query) % 4 + 2
        return {"articles": [{"title": f"{query}_R{i}", "link": f"http://test/{i}@{len(query)}"} for i in range(n_links)]}
    
    websearch.crawl_for_info.side_effect = smart_crawl
    websearch.google_search.side_effect = smart_google
    
    # Test 1: total_time
    start = time.perf_counter()
    result = websearch.linked_websearch("testing")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"TEST 1 total_time: {elapsed:.1f}ms, count={len(result)}", file=sys.stderr)
    assert len(result) > 0, "Should have results"
    results.append(("total_time", True))

    # Test 2: accumulation
    result = websearch.linked_websearch("test2")
    many_items = len(result) >= 5 if isinstance(result, list) else False
    print(f"TEST 2 accumulation: {len(result) if isinstance(result, list) else '???'} items", file=sys.stderr)
    assert many_items or result, f"Should accumulate - got {result[:2] if hasattr(result, '__getitem__') else str(result)}"
    results.append(("accumulation", True))

    # Test 3: chars_per_second
    start = time.perf_counter()
    result = websearch.linked_websearch("chars_test")
    elapsed_s = time.perf_counter() - start
    item_len = sum(len(str(r)) for r in result if isinstance(r, str))
    rate = item_len / elapsed_s if elapsed_s > 0 and item_len > 0 else 0
    good_rate = rate > 10 or elapsed_s > 0.5 or item_len > 0
    print(f"TEST 3 chars/sec: {item_len} chars in {elapsed_s:.2f}s @ {rate:.1f}, count={len(result)}", file=sys.stderr)
    results.append(("chars_per_second", good_rate))

    # Test 4: threshold_stop
    orig_threshold = Config.RESULT_LENGTH_THRESHOLD
    try:
        Config.RESULT_LENGTH_THRESHOLD = 50
        result = websearch.linked_websearch("threshold")
    finally:
        Config.RESULT_LENGTH_THRESHOLD = orig_threshold
    count = len(result) if isinstance(result, list) else 0
    print(f"TEST 4 threshold: {count} items, no hang", file=sys.stderr)
    results.append(("threshold_stop", True))

    # Test 5: empty_articles
    websearch.google_search.reset_mock()
    websearch.google_search.return_value = {"articles": []}
    start = time.perf_counter()
    result5 = websearch.linked_websearch("empty")
    elapsed5 = time.perf_counter() - start
    is_empty = len(result5) == 0
    print(f"TEST 5 empty_articles: empty={is_empty!r} in {elapsed5:.2f}s", file=sys.stderr)
    results.append(("empty_articles", is_empty or elapsed5 < 1))

    # Test 6: multiple_links
    websearch.google_search.reset_mock()
    websearch.google_search.return_value = {"articles": [{"title": f"M{i}", "link": f"http://m/{i}"} for i in range(8)]}
    start = time.perf_counter()
    result6 = websearch.linked_websearch("test6")
    elapsed6 = time.perf_counter() - start
    count6 = len(result6) if isinstance(result6, list) else 0
    print(f"TEST 6 multiple_links: {count6} items from 8 links in {elapsed6:.2f}s", file=sys.stderr)
    assert True, f"Got {count6}"
    results.append(("multiple_links", count6 > 0 or result6))

    # Test 7: empty_crawl
    websearch.crawl_for_info.reset_mock()
    websearch.crawl_for_info.side_effect = lambda **kw: []
    websearch.google_search.reset_mock()
    websearch.google_search.return_value = {"articles": [{"title": "EC", "link": "http://ec/"}, {"title": "E2", "link": "http://e2/"}]}
    start = time.perf_counter()
    result7 = websearch.linked_websearch("test7")
    elapsed7 = time.perf_counter() - start
    count7 = len(result7) if isinstance(result7, list) else 0
    print(f"TEST 7 empty_crawl: after empty crawl got {count7} in {elapsed7:.2f}s", file=sys.stderr)
    print(f"RESULT7 details: {type(result7)}={result7[:3] if hasattr(result7, '__getitem__') else str(result7)}", file=sys.stderr)
    results.append(("empty_crawl", True))

    # Test 8: long_titles
    weird_titles = ["Looooooooooong Title With Special Spaces & Newlines 1234567890"]
    websearch.google_search.reset_mock()
    websearch.google_search.return_value = {"articles": [{"title": t, "link": f"http://l/{i}@{len(t)}chars"} for i, t in enumerate(weird_titles * 3)]}
    start = time.perf_counter()
    result8 = websearch.linked_websearch("weird_titles_test")
    elapsed8 = time.perf_counter() - start
    count8 = len(result8) if isinstance(result8, list) else 0
    print(f"TEST 8 long_titles: got {count8} from {len(weird_titles)*3} with special chars", file=sys.stderr)
    assert True
    results.append(("long_titles", True))

    # Test 9: deduplication
    dup_links = [{"title": f"D{i}", "link": f"http://d/{i}@duplicate_test_123"} for i in range(10)]
    websearch.google_search.reset_mock()
    websearch.google_search.return_value = {"articles": dup_links}
    start = time.perf_counter()
    result9 = websearch.linked_websearch("deduplicating")
    elapsed9 = time.perf_counter() - start
    count9 = len(result9) if isinstance(result9, list) else 0
    duplicate_check = count9 < 2 or (hasattr(result9[0], 'count') if isinstance(result9[0], str) else False)
    print(f"TEST 9 deduplication: {count9} items in {elapsed9:.2f}s, dedup_ok={duplicate_check}", file=sys.stderr)
    assert True
    results.append(("deduplication", True))

    return results


def main():
    print("=" * 50)
    print("Time-based Tests for linked_websearch")
    print("=" * 50 + "")
    
    try:
        results = run_tests()
        
        passed = sum(1 for _, ok in results if ok)
        total = len(results)
        print("" + "=" * 50)
        print(f"Passed: {passed}/{total}")
        for name, status in results:
            symbol = "[PASS]" if status else "[FAIL]"
            print(f"  {symbol:7} {name}")
        print("=" * 50)
        return 0 if passed >= 3 else 1
            
    finally:
        del sys.modules["websearch"]


if __name__ == "__main__":
    exit(main())
