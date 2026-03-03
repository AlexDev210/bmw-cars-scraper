BOT_NAME = "bmw_scraper"

SPIDER_MODULES = ["bmw_scraper.spiders"]
NEWSPIDER_MODULE = "bmw_scraper.spiders"

CONCURRENT_REQUESTS = 2
COOKIES_ENABLED = True

DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.retry.RetryMiddleware": None,
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "bmw_scraper.middlewares.RandomUserAgentMiddleware": 400,
    "bmw_scraper.middlewares.BackoffRetryMiddleware": 550,
}

ITEM_PIPELINES = {
    "bmw_scraper.pipelines.ValidationAndCleaningPipeline": 100,
    "bmw_scraper.pipelines.SQLitePipeline": 200,
}

SQLITE_DB_PATH = "bmw_cars.db"

RETRY_ENABLED = True
RETRY_TIMES = 4
RETRY_HTTP_CODES = [429, 500, 502, 503, 504]

DOWNLOAD_DELAY = 1
RANDOMIZE_DOWNLOAD_DELAY = True

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.8
AUTOTHROTTLE_MAX_DELAY = 10
AUTOTHROTTLE_TARGET_CONCURRENCY = 1.8

ROBOTSTXT_OBEY = False
REQUEST_FINGERPRINTER_IMPLEMENTATION = "2.7"
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"
FEED_EXPORT_ENCODING = "utf-8"

LOG_LEVEL = "INFO"

DEFAULT_REQUEST_HEADERS = {
    "Accept-Language": "en-GB,en;q=0.9",
}
