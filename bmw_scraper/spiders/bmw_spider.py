import json
import scrapy

from bmw_scraper.items import BmwCarItem

HOME_URL  = "https://usedcars.bmw.co.uk/"
API_URL   = "https://usedcars.bmw.co.uk/vehicle/api/list/"
PAGE_SIZE = 23
MAX_PAGES = 5

ADVERT_DATA_RE = r"(?s)UVL\.AD\s*=\s*(\{.+?\});\s*\n"


class BmwSpider(scrapy.Spider):
    name = "bmw"
    allowed_domains = ["usedcars.bmw.co.uk"]

    def __init__(self, max_pages=MAX_PAGES, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_pages = int(max_pages)

    _BASE_HEADERS = {
        "Accept": "application/json, text/plain, */*",
        "Dnt": "1",
    }

    async def start(self):
        yield scrapy.Request(
            url=HOME_URL,
            callback=self.after_homepage,
            dont_filter=True,
        )

    def after_homepage(self, response):
        csrf = self._get_csrf(response)
        self.logger.info(f"[BMW] csrftoken: {csrf}")
        yield self._api_request(csrf, page=1, first=True)

    def _api_request(self, csrf, page, first=False):
        url = f"{API_URL}?page={page}&size={PAGE_SIZE}"
        return scrapy.Request(
            url=url,
            callback=self.parse_api,
            headers=self._build_headers(csrf, page),
            meta={"page": page, "csrf": csrf, "first": first},
            dont_filter=True,
        )

    def parse_api(self, response):
        page = response.meta["page"]
        csrf = response.meta["csrf"]
        first = response.meta["first"]

        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"[Page {page}] JSON error: {e}\n{response.text[:300]}")
            return

        results = data.get("results", [])
        self.logger.info(f"[Page {page}] {len(results)} cars received")

        if first:
            self.logger.info(f"[BMW] Scheduling pages 2–{self.max_pages}")
            for p in range(2, self.max_pages + 1):
                yield self._api_request(csrf, page=p)

        yield from self._schedule_adverts(results)

    def _schedule_adverts(self, results):
        for car in results:
            advert_id = car.get("advert_id")
            if not advert_id:
                continue

            yield scrapy.Request(
                url=f"{HOME_URL}vehicle/{advert_id}",
                callback=self.parse_advert,
                meta={"advert_id": advert_id},
            )

    def _extract_fields(self, ad: dict) -> dict:
        cc = self._get_path(ad, "engine", "size", "cc")
        range_value = self._get_path(ad, "battery", "range", "value")

        return {
            "model": self._clean(ad.get("title")),
            "name": self._clean(self._get_path(ad, "specification", "derivative")),
            "mileage": self._get_path(ad, "condition_and_state", "mileage"),
            "registered": self._clean(self._get_path(ad, "dates", "registration")),
            "registration": self._clean(self._get_path(ad, "identification", "registration")),
            "engine": f"{cc:,} cc" if cc else None,
            "range": range_value or None,
            "fuel": self._get_path(ad, "engine", "fuel") or None,
            "exterior": self._clean(self._get_path(ad, "colour", "manufacturer_colour")),
            "transmission": self._clean(self._get_path(ad, "specification", "transmission")),
            "upholstery": self._clean(self._get_path(ad, "specification", "interior")),
        }

    def parse_advert(self, response):
        raw_json = response.css("script[type='text/javascript']").re_first(ADVERT_DATA_RE)

        if not raw_json:
            self.logger.warning(f"[{response.url}] UVL.AD not found")
            return

        try:
            ad = json.loads(raw_json)
        except json.JSONDecodeError as e:
            self.logger.error(f"[{response.url}] JSON error: {e}")
            return

        item = BmwCarItem(**self._extract_fields(ad))

        self.logger.info(
            f"[{item['registration']}] {item['model']} {item['name']} | "
            f"{item['mileage']} mi | {item['registered']}"
        )

        yield item

    @staticmethod
    def _get_path(data: dict, *keys, default=None):
        for key in keys:
            if not isinstance(data, dict):
                return default
            data = data.get(key, default)
        return data

    @staticmethod
    def _build_referer(page: int) -> str:
        if page == 1:
            return f"{HOME_URL}result/?payment_type=cash&size=23&source=home"
        return f"{HOME_URL}result/?page={page}&size={PAGE_SIZE}"

    @staticmethod
    def _build_headers(csrf: str, page: int) -> dict:
        return {
            **BmwSpider._BASE_HEADERS,
            "Referer": BmwSpider._build_referer(page),
            "X-Csrftoken": csrf,
        }

    @staticmethod
    def _get_csrf(response) -> str:
        for cookie_header in response.headers.getlist("Set-Cookie"):
            cookie_str = cookie_header.decode("utf-8", errors="ignore")
            for part in cookie_str.split(";"):
                part = part.strip()
                if part.lower().startswith("csrftoken="):
                    return part.split("=", 1)[1].strip()
        return ""

    @staticmethod
    def _clean(value) -> str | None:
        if value is None:
            return None
        return str(value).strip() or None
