from bs4 import BeautifulSoup

from extractors.meta_tags import extract_meta
from extractors.open_graph import extract_open_graph
from extractors.navigation_parser import extract_navigation


class BaseAnalyzer:
    platform_name = "Unknown"

    def base_result(self, url, html, headers, page_type, level1):
        soup = BeautifulSoup(html or "", "lxml")

        return {
            "level1": level1,
            "platform": self.platform_name,
            # User-facing tech label from the detector (real framework/CMS, or a
            # friendly fallback). `platform` above is the internal analyzer key.
            "displayPlatform": (level1 or {}).get("displayPlatform"),
            "page": {
                "url": url,
                "pageType": page_type
            },
            "seo": extract_meta(soup),
            "openGraph": extract_open_graph(soup),
            "navigation": extract_navigation(soup, url),
            "content": {},
            "ecommerce": {},
            "products": [],
            "technical": {
                "finalUrl": url,
                "responseHeaders": dict(headers) if headers else {}
            },
            "source": {
                "extractor": self.__class__.__name__,
                "confidence": 0.5
            }
        }
