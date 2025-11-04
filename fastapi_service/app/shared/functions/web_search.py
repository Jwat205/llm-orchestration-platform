# shared/functions/web_search.py
def web_search(query: str, max_results: int = 5) -> list:
    # Placeholder: integrate with a real search API
    return [{"title": f"Result {i+1}", "url": f"https://example.com/{i+1}"} for i in range(max_results)]
