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

PROXY_ATTEMPTS = [
    ("residential", 2),
    ("stealth",     2),
]


def parse_reviews_from_text(text: str) -> dict:
    """
    Angi shows rating and count in heading as: [4.7(388)](#reviews)
    Fallback: FAQ section says "currently rated 4.7 overall out of 5"
    """
    total_reviews = None
    average_rating = None

    # Primary: [4.7(388)](#reviews) format in heading
    m = re.search(r'\[([\d.]+)\((\d+)\)\]\(#reviews\)', text)
    if m:
        average_rating = m.group(1)
        total_reviews = m.group(2)
    else:
        # Fallback: FAQ section
        m = re.search(r'currently rated ([\d.]+) overall out of 5', text)
        if m:
            average_rating = m.group(1)
        m2 = re.search(r'([\d,]+)\s+Reviews?', text)
        if m2:
            total_reviews = m2.group(1).replace(",", "")

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

    proxy_attempts = PROXY_ATTEMPTS

    last_error = None
    for proxy, tries in proxy_attempts:
        for attempt in range(1, tries + 1):
            try:
                print(f"    [{proxy}] Attempt {attempt}/{tries} ...")
                text = fetch_text(business["angi_url"], proxy)
                parsed = parse_reviews_from_text(text)

                if parsed["total_reviews"] is None:
                    snippet = " ".join(text.split())[:300]
                    print(f"    ⚠ Page loaded but could not parse data. Snippet: {snippet}")

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
        time.sleep(12)

    output_file = "angi_reviews.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n=== Done! Results saved to {output_file} ===")
    print(f"Total processed: {len(results)} | Skipped: {sum(1 for r in results if r['angi_url'] is None)}")


if __name__ == "__main__":
    main()
