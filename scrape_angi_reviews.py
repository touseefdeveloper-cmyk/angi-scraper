import requests
import json
import time
import os
import re

API_KEY = os.environ.get("WEBSCRAPING_AI_KEY_ANGI", "")
TEXT_URL = "https://api.webscraping.ai/text"

BUSINESSES = [
    {"id": "cabinet-refresh",          "angi_url": "https://www.angi.com/companylist/us/ca/los-angeles/cabinet-refresh-reviews-6568336.htm"},
    {"id": "american-vision-windows",  "angi_url": "https://www.angi.com/companylist/us/ca/tustin/american-vision-windows-reviews-3911626.htm"},
    {"id": "one-week-bath",            "angi_url": "https://www.angi.com/companylist/us/ca/van-nuys/one-week-bath-reviews-184509.htm"},
    {"id": "abc-pro",                  "angi_url": "https://www.angi.com/companylist/us/ca/reseda/abraham-building-consulting-inc-reviews-1.htm"},
    {"id": "1-degree-construction",    "angi_url": None},
    {"id": "mr-cabinet-care",          "angi_url": "https://www.angi.com/companylist/us/ca/woodland-hills/my-home-builders-inc-reviews-1.htm"},
    {"id": "payless-kitchen-cabinets", "angi_url": "https://www.angi.com/companylist/us/ca/glendale/payless-kitchen-cabinets-and-bath-makeover-reviews-1.htm"},
    {"id": "payless-bath-makeover",    "angi_url": "https://www.angi.com/companylist/us/ca/glendale/payless-kitchen-cabinets-and-bath-makeover-reviews-1.htm"},
    {"id": "adar-builders",            "angi_url": "https://www.angi.com/companylist/us/ca/los-angeles/adar-builders-inc-reviews-9993206.htm"},
    {"id": "gm-home-remodeling",       "angi_url": None},
]

RETRY_DELAY = 30


def parse_reviews_from_text(text: str) -> dict:
    """
    Angi rating patterns in order of reliability:
      1. [4.9(168)] — compact format in heading
      2. "rated 4.9 overall out of 5" — FAQ section
      3. "4.9\n168 Reviews" — number right before review count
    """
    total_reviews = None
    average_rating = None

    # Total reviews — "168 Reviews"
    m = re.search(r"([\d,]+)\s+Reviews", text, re.IGNORECASE)
    if m:
        total_reviews = m.group(1).replace(",", "")

    # Rating — try multiple patterns in order
    rating_patterns = [
        r"\[([\d.]+)\(\d+\)\]",                        # [4.9(168)]
        r"rated\s+([\d.]+)\s+overall\s+out\s+of\s+5",  # rated 4.9 overall out of 5
        r"([\d.]+)\s*\n+\s*[\d,]+\s+Reviews",          # 4.9 \n 168 Reviews
        r"([\d.]+)\s+out\s+of\s+5",                    # 4.9 out of 5
    ]
    for pattern in rating_patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1)
            # Sanity check: rating must be between 1.0 and 5.0
            if 1.0 <= float(val) <= 5.0:
                average_rating = val
                break

    return {"total_reviews": total_reviews, "average_rating": average_rating}


def fetch_text(url: str, proxy: str) -> str:
    params = {
        "api_key": API_KEY,
        "url": url,
        "js": "true",
        "proxy": proxy,
        "timeout": 30000,
        "country": "us",
        "wait_for": "h1",
    }
    response = requests.get(TEXT_URL, params=params, timeout=90)
    response.raise_for_status()
    return response.text


def scrape_angi(business: dict) -> dict:
    if not business["angi_url"]:
        print(f"  [{business['id']}] Skipped — no URL provided.")
        return {"id": business["id"], "angi_url": None, "total_reviews": None, "average_rating": None, "error": "No URL provided"}

    print(f"  [{business['id']}] Scraping ...")

    proxy_attempts = [
        ("residential", 2),
        ("stealth",     2),
    ]

    last_error = None
    for proxy, tries in proxy_attempts:
        for attempt in range(1, tries + 1):
            try:
                print(f"    [{proxy}] Attempt {attempt}/{tries} ...")
                text = fetch_text(business["angi_url"], proxy)
                parsed = parse_reviews_from_text(text)

                if parsed["total_reviews"] is None or parsed["average_rating"] is None:
                    snippet = " ".join(text.split())[:400]
                    print(f"    ⚠ Partial parse — reviews:{parsed['total_reviews']} rating:{parsed['average_rating']}. Snippet: {snippet}")

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
        time.sleep(15)  # increased delay between businesses

    output_file = "angi_reviews.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n=== Done! Results saved to {output_file} ===")
    print(f"Total processed: {len(results)} | Skipped: {sum(1 for r in results if r['angi_url'] is None)}")


if __name__ == "__main__":
    main()
