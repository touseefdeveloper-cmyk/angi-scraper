import requests
import json
import time
import os
import re

API_KEY = os.environ.get("WEBSCRAPING_AI_KEY_ANGI", "")
TEXT_URL = "https://api.webscraping.ai/text"
HTML_URL = "https://api.webscraping.ai/html"

BUSINESSES = [
    {"id": "cabinet-refresh",          "angi_url": "https://www.angi.com/companylist/us/ca/los-angeles/cabinet-refresh-reviews-6568336.htm"},
    {"id": "american-vision-windows",  "angi_url": "https://www.angi.com/companylist/us/ca/tustin/american-vision-windows-reviews-3911626.htm"},
    {"id": "one-week-bath",            "angi_url": "https://www.angi.com/companylist/us/ca/van-nuys/one-week-bath-reviews-184509.htm"},
    {"id": "abc-pro",                  "angi_url": "https://www.angi.com/companylist/us/ca/reseda/abraham-building-consulting-inc-reviews-1.htm"},
    {"id": "1-degree-construction",    "angi_url": None},
    {"id": "mr-cabinet-care",          "angi_url": "https://www.angi.com/companylist/us/ca/woodland-hills/my-home-builders-inc-reviews-1.htm"},
    {"id": "payless-kitchen-cabinets", "angi_url": "https://www.angi.com/companylist/us/ca/glendale/payless-kitchen-cabinets-and-bath-makeover-reviews-1.htm"},
    {"id": "adar-builders",            "angi_url": "https://www.angi.com/companylist/us/ca/los-angeles/adar-builders-inc-reviews-9993206.htm"},
    {"id": "gm-home-remodeling",       "angi_url": None},
]

RETRY_DELAY = 30


def parse_reviews_from_text(text: str) -> dict:
    total_reviews = None
    average_rating = None

    # Total reviews — try multiple patterns in order of reliability
    for pattern in [
        r"([\d,]+)\s+Reviews",          # "168 Reviews" or "1 Reviews"
        r"\[[\d.]+\((\d+)\)\]",         # [4.9(168)] — extract count from heading link
        r"Showing \d+-\d+ of (\d+)",    # "Showing 1-1 of 1 reviews"
        r"(\d+)\s+review",              # generic fallback
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            total_reviews = m.group(1).replace(",", "")
            break

    # Rating — multiple patterns in order of reliability
    rating_patterns = [
        r"\[([\d.]+)\(\d+\)\]",                        # [4.9(168)] in markdown links
        r"rated\s+([\d.]+)\s+overall\s+out\s+of\s+5",  # FAQ section
        r"([\d.]+)\s*\n+\s*[\d,]+\s+Reviews",          # number above review count
        r"([\d.]+)\s+out\s+of\s+5",                    # generic
    ]
    for pattern in rating_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1)
            if 1.0 <= float(val) <= 5.0:
                average_rating = val
                break

    return {"total_reviews": total_reviews, "average_rating": average_rating}


def parse_reviews_from_html(html: str) -> dict:
    """Fallback: parse raw HTML for rating/review data."""
    total_reviews = None
    average_rating = None

    # Total reviews from HTML
    for pattern in [
        r">([\d,]+)\s+Reviews<",
        r"Showing \d+-\d+ of (\d+)",
        r'"reviewCount"\s*:\s*"?(\d+)"?',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            total_reviews = m.group(1).replace(",", "")
            break

    # e.g. "ratingValue":"4.9" or ratingValue: 4.9
    for pattern in [
        r'"ratingValue"\s*:\s*"?([\d.]+)"?',
        r'ratingValue["\s:]+([0-9.]+)',
        r'aggregateRating[^}]*?"ratingValue"[^}]*?"([\d.]+)"',
        r'overall rated\?.*?rated\s+([\d.]+)\s+overall',
    ]:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if m:
            val = m.group(1)
            try:
                if 1.0 <= float(val) <= 5.0:
                    average_rating = val
                    break
            except ValueError:
                continue

    return {"total_reviews": total_reviews, "average_rating": average_rating}


def base_params(url: str, proxy: str) -> dict:
    return {
        "api_key": API_KEY,
        "url": url,
        "js": "true",
        "proxy": proxy,
        "timeout": 30000,
        "country": "us",
        "wait_for": "h1",
    }


def scrape_angi(business: dict) -> dict:
    if not business["angi_url"]:
        print(f"  [{business['id']}] Skipped — no URL provided.")
        return {"id": business["id"], "angi_url": None, "total_reviews": None, "average_rating": None, "error": "No URL provided"}

    print(f"  [{business['id']}] Scraping ...")

    proxy_attempts = [("residential", 2), ("stealth", 2)]
    last_error = None

    for proxy, tries in proxy_attempts:
        for attempt in range(1, tries + 1):
            try:
                print(f"    [{proxy}] Attempt {attempt}/{tries} ...")

                # First try /text endpoint (cheaper)
                response = requests.get(TEXT_URL, params=base_params(business["angi_url"], proxy), timeout=90)
                response.raise_for_status()
                text = response.text
                parsed = parse_reviews_from_text(text)

                # If rating is missing, fall back to /html for richer content
                if parsed["average_rating"] is None:
                    print(f"    ⚠ Rating not found in text, trying HTML endpoint ...")
                    html_response = requests.get(HTML_URL, params=base_params(business["angi_url"], proxy), timeout=90)
                    html_response.raise_for_status()
                    html_parsed = parse_reviews_from_html(html_response.text)
                    if html_parsed["average_rating"]:
                        parsed["average_rating"] = html_parsed["average_rating"]
                    if parsed["total_reviews"] is None and html_parsed["total_reviews"]:
                        parsed["total_reviews"] = html_parsed["total_reviews"]

                if parsed["total_reviews"] is None and parsed["average_rating"] is None:
                    snippet = " ".join(text.split())[:400]
                    print(f"    ⚠ Could not parse data. Snippet: {snippet}")

                result = {
                    "id": business["id"],
                    "angi_url": business["angi_url"],
                    "total_reviews": parsed["total_reviews"],
                    "average_rating": parsed["average_rating"],
                    "error": None,
                }
                print(f"    ✓ Reviews: {result['total_reviews']} | Rating: {result['average_rating']}")
                return result

            except requests.exceptions.RequestException as e:
                last_error = str(e)
                print(f"    ✗ [{proxy}] Attempt {attempt} failed: {e}")
                if attempt < tries:
                    print(f"    Retrying in {RETRY_DELAY}s ...")
                    time.sleep(RETRY_DELAY)

        print(f"    Switching to next proxy type ...")
        time.sleep(RETRY_DELAY)

    print(f"    ✗ All proxy attempts exhausted.")
    return {"id": business["id"], "angi_url": business["angi_url"], "total_reviews": None, "average_rating": None, "error": last_error}


def main():
    print("=== Angi Review Scraper ===\n")
    results = []

    for business in BUSINESSES:
        result = scrape_angi(business)
        results.append(result)
        time.sleep(15)

    output_file = "angi_reviews.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n=== Done! Results saved to {output_file} ===")
    print(f"Total processed: {len(results)} | Skipped: {sum(1 for r in results if r['angi_url'] is None)}")


if __name__ == "__main__":
    main()
