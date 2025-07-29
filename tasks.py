import re
from time import sleep
from pathlib import Path
from robocorp.tasks import task
from robocorp import browser
from utils.helper import (
    save_reviews_to_csv_incremental,
    insert_reviews_into_db_incremental,
    create_reviews_table,
    fetch_existing_reviews,
    logger,
)

# === Configuration ===
APP_ID = "220"
SCROLL_DELAY = 1.5
BATCH_SIZE = 10

REVIEW_PAGE_URL = f"https://steamcommunity.com/app/{APP_ID}/reviews/?browsefilter=toprated&snr=1_5_100010_"
STORE_PAGE_URL = f"https://store.steampowered.com/app/{APP_ID}/HalfLife_2/#app_reviews_hash"

def get_total_review_count():
    store_page = browser.goto(STORE_PAGE_URL)
    store_page.wait_for_selector("#user_reviews_filter_score", timeout=10000)

    text = store_page.query_selector("#user_reviews_filter_score span").inner_text()
    match = re.search(r"Showing\s+([\d,]+)\s+reviews", text)
    store_page.close()

    if match:
        return int(match.group(1).replace(",", ""))
    raise Exception("Could not parse total review count from store page.")

@task
def scrape_steam_reviews():
    browser.configure(
        browser_engine="chromium",
        headless=True,
        screenshot="only-on-failure"
    )

    try:
        total_reviews = get_total_review_count()
        logger.info(f"🧮 Total reviews available: {total_reviews}")

        page = browser.goto(REVIEW_PAGE_URL)
        page.wait_for_selector("div.apphub_Card", timeout=10000)

        seen_reviews = fetch_existing_reviews(int(APP_ID))
        reviews_batch = []
        total_new = 0

        logger.info(f"🔍 Scraping reviews for App ID: {APP_ID}")
        logger.info(f"📌 Existing review count in DB: {len(seen_reviews)}")

        create_reviews_table()

        while total_new < total_reviews:
            review_blocks = page.query_selector_all("div.apphub_Card")

            for block in review_blocks:
                try:
                    username_elem = block.query_selector("div.apphub_CardContentAuthorName")
                    username = (
                        username_elem.query_selector_all("a")[-1].inner_text().strip()
                        if username_elem and username_elem.query_selector_all("a")
                        else "Unknown"
                    )

                    hours_elem = block.query_selector("div.hours")
                    hours = hours_elem.inner_text().strip() if hours_elem else "Unknown"

                    date_elem = block.query_selector("div.date_posted")
                    date = date_elem.inner_text().replace("Posted:", "").strip() if date_elem else "Unknown"

                    content_elem = block.query_selector("div.apphub_CardTextContent")
                    content = content_elem.inner_text().strip() if content_elem else ""

                    if not content or content in seen_reviews:
                        continue

                    seen_reviews.add(content)
                    found_helpful_text = block.query_selector("div.found_helpful")
                    helpful = funny = 0
                    if found_helpful_text:
                        text = found_helpful_text.inner_text()
                        helpful_match = re.search(r"(\d[\d,]*) people found this review helpful", text)
                        funny_match = re.search(r"(\d[\d,]*) people found this review funny", text)
                        helpful = int(helpful_match.group(1).replace(",", "")) if helpful_match else 0
                        funny = int(funny_match.group(1).replace(",", "")) if funny_match else 0

                    review_data = {
                        "Username": username,
                        "Hours": hours,
                        "Date": date,
                        "Review": content,
                        "Helpful": helpful,
                        "Funny": funny
                    }

                    reviews_batch.append(review_data)
                    total_new += 1

                    if len(reviews_batch) >= BATCH_SIZE:
                        insert_reviews_into_db_incremental(reviews_batch, int(APP_ID))
                        save_reviews_to_csv_incremental(reviews_batch, int(APP_ID))
                        reviews_batch.clear()

                        percentage = (total_new / total_reviews) * 100
                        logger.info(f"✅ Progress: {total_new}/{total_reviews} ({percentage:.2f}%)")

                    if total_new >= total_reviews:
                        break

                except Exception as e:
                    logger.warning(f"⚠️ Skipping review due to error: {e}")

            logger.info(f"📝 Collected so far: {total_new} reviews")
            if total_new >= total_reviews:
                break

            page.evaluate("window.scrollBy(0, document.body.scrollHeight)")
            sleep(SCROLL_DELAY)

        if reviews_batch:
            insert_reviews_into_db_incremental(reviews_batch, int(APP_ID))
            save_reviews_to_csv_incremental(reviews_batch, int(APP_ID))
            logger.info(f"✅ Saved final batch. Total scraped: {total_new}")

    finally:
        page.close()
        logger.info("🛑 Browser closed.")
