# BMW Approved Used Cars Scraper

A Scrapy-based spider that collects used car listings from the [BMW UK Approved Used Cars](https://usedcars.bmw.co.uk/) website and stores them in a SQLite database.

---

## What It Does

The spider scrapes the first 5 pages of cash-payment listings, follows each car's detail page, extracts full specification data, and saves everything to a local `bmw_cars.db` SQLite database — deduplicating by registration plate.

---

## Why I Used the Internal API Instead of Parsing HTML

The listing page (`/result/`) is a React SPA — it renders entirely via JavaScript, so raw HTML scraping yields no car data. By inspecting the Network tab in DevTools, I found that the frontend calls an internal REST API:

```
GET /vehicle/api/list/?page={n}&size=23
```

This API returns clean, structured JSON with all the data needed — no JavaScript rendering required. Using it directly is:
- **Faster** — one JSON request vs. parsing a full rendered HTML page
- **More stable** — JSON structure is less likely to change than UI markup
- **Simpler** — no need for Selenium or Playwright

This also means there was no reason to use headless browser tools like Selenium or Playwright. They are slow to start, heavy on memory, require a browser binary, and add significant complexity — all unnecessary overhead when a clean JSON API is available and accessible with a regular HTTP client.

For the detail pages (`/vehicle/{advert_id}`), the full car spec is embedded in the HTML as an inline JavaScript object `UVL.AD = {...}`, which is extracted via a CSS + regex selector and parsed as JSON.

---

## Core Task — How Each Requirement Was Solved

### Scraping the First 5 Pages

The spider starts by hitting the homepage to obtain a CSRF token from the `Set-Cookie` header. It then requests page 1 of the API. On receiving the first response, it immediately schedules pages 2–5 in parallel — no waiting for pages to complete sequentially.

```
HOME → grab CSRF → API page 1 → schedule pages 2–5 in parallel → follow advert links
```

The number of pages can be overridden at runtime without touching the code:

```bash
scrapy crawl bmw -a max_pages=3
```

### Following Listing Links to Detail Pages

From each API response, `advert_id` values are extracted. Each ID is used to construct a detail page URL (`/vehicle/{advert_id}`). Scrapy's built-in request fingerprinting handles deduplication — no manual tracking needed.

### Extracting All Required Fields

All fields are pulled from the embedded `UVL.AD` JSON object on the detail page:

| Field | Source in JSON |
|---|---|
| `model` | `title` |
| `name` | `specification.derivative` |
| `mileage` | `condition_and_state.mileage` |
| `registered` | `dates.registration` |
| `engine` | `engine.size.cc` → formatted as `"2,993 cc"` |
| `range` | `battery.range.value` |
| `exterior` | `colour.manufacturer_colour` |
| `fuel` | `engine.fuel` |
| `transmission` | `specification.transmission` |
| `registration` | `identification.registration` |
| `upholstery` | `specification.interior` |

Electric cars have `range` populated and `engine` set to `NULL`. ICE cars are the opposite.

### SQLite Storage & Deduplication

The `SQLitePipeline` creates a `bmw_cars` table with `registration TEXT UNIQUE NOT NULL`. Inserts use `INSERT OR IGNORE` — if a car with the same registration plate already exists, it is silently skipped. Commits happen every 10 inserts during the crawl, with a final commit on spider close.

---

## Bonus Tasks — How Each Was Solved

### 6.1 Random User-Agent Rotation (`RandomUserAgentMiddleware`)

A custom downloader middleware maintains a list of 6 real browser User-Agent strings (Chrome on Windows/Mac/Linux, Edge, Firefox). On every outgoing request, one is selected at random and injected into the headers. The selected UA is logged at `DEBUG` level. The built-in `UserAgentMiddleware` is disabled in settings to prevent conflicts.

### 6.2 Data Validation & Cleaning (`ValidationAndCleaningPipeline`)

A separate pipeline runs before the SQLite pipeline (priority `100` vs `200`):

- **Validation** — drops items missing `model`, `name`, or `registration`, logging a warning with the registration plate
- **Mileage cleaning** — extracts only digits via `re.sub(r"[^\d]", "")` and converts to `int` (e.g. `"8,143 miles"` → `8143`). Handles any format the site returns. Stores `NULL` if no digits found
- **Fuel normalization** — lowercases the fuel type (e.g. `"ELECTRIC"` → `"electric"`)

---

## What I Added Beyond the Requirements

### Exponential Backoff Retry Middleware (`BackoffRetryMiddleware`)

The site enforces a rate limit and returns `HTTP 429` under load. The default Scrapy retry middleware simply retries immediately, which just triggers more 429s.

I replaced it with a custom async middleware that waits progressively longer before each retry:

| Retry attempt | Delay |
|---|---|
| 1st | 3s |
| 2nd | 5s |
| 3rd | 20s |
| 4th | 60s |

The delay is implemented with `asyncio.sleep` — non-blocking, so other requests continue normally while waiting.

### CSRF Token Extraction

The site uses Django's CSRF protection. The token is extracted from the `Set-Cookie` response header on the homepage and passed as `X-Csrftoken` on every API request — matching exactly what the browser does.

### `AutoThrottle` + `DOWNLOAD_DELAY`

AutoThrottle dynamically adjusts request rate based on server response times. `DOWNLOAD_DELAY` sets a minimum floor so the spider never sends requests faster than the server can handle, even at startup before AutoThrottle has enough data to calibrate.

---

## Running the Spider

```bash
pip install -r requirements.txt
cd bmw_scraper
scrapy crawl bmw
```

Results are saved to `bmw_cars.db` in the project directory.

---