from analyzers.base_analyzer import BaseAnalyzer

from analyzers.unknown.homepage import analyze_unknown_homepage
from analyzers.unknown.collection import analyze_unknown_collection
from analyzers.unknown.product import analyze_product
from analyzers.unknown.general import analyze_unknown_general


class UnknownAnalyzer(BaseAnalyzer):
    platform_name = "Unknown"

    def analyze(self, url, html, headers, page_type, level1):
        if page_type == "homepage":
            return analyze_unknown_homepage(self, url, html, headers, page_type, level1)

        if page_type == "collection":
            return analyze_unknown_collection(self, url, html, headers, page_type, level1)

        if page_type == "product":
            return analyze_product(self, url, html, headers, page_type, level1)

        # No separate Unknown blog extractor yet.
        # Use general extractor but preserve page_type='blog' in final JSON.
        if page_type == "blog":
            return analyze_unknown_general(self, url, html, headers, "blog", level1)

        return analyze_unknown_general(self, url, html, headers, page_type, level1)
