import random
import logging
import asyncio

from scrapy import signals
from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
]

RETRY_DELAYS = [3, 5, 20, 60]


class RandomUserAgentMiddleware:

    @staticmethod
    def process_request(request):
        ua = random.choice(USER_AGENTS)
        request.headers["User-Agent"] = ua
        logger.debug(f"[UA] {ua[:80]}")


class BackoffRetryMiddleware(RetryMiddleware):
    def __init__(self, settings):
        super().__init__(settings)
        self._spider = None

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls(crawler.settings)
        crawler.signals.connect(
            lambda spider: setattr(obj, "_spider", spider),
            signal=signals.spider_opened,
        )
        return obj

    async def process_response(self, request, response):
        if response.status in self.retry_http_codes:
            retries = request.meta.get("retry_times", 0)
            delay = RETRY_DELAYS[retries] if retries < len(RETRY_DELAYS) else RETRY_DELAYS[-1]
            logger.debug(f"[Retry] {response.status} — waiting {delay}s before retry #{retries + 1}")
            await asyncio.sleep(delay)
            return self._retry(request, response_status_message(response.status), self._spider) or response

        return response