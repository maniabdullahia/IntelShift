from analyzers.base_analyzer import BaseAnalyzer

from analyzers.shopify.homepage import analyze_homepage
from analyzers.shopify.collection import analyze_collection
from analyzers.shopify.product import analyze_product
from analyzers.shopify.blog import analyze_blog
from analyzers.shopify.general import analyze_general


class ShopifyAnalyzer(BaseAnalyzer):
    platform_name = "Shopify"

    def analyze(self, url, html, headers, page_type, level1):
        if page_type == "homepage":
            return analyze_homepage(self, url, html, headers, page_type, level1)

        if page_type == "collection":
            return analyze_collection(self, url, html, headers, page_type, level1)

        if page_type == "product":
            return analyze_product(self, url, html, headers, page_type, level1)

        if page_type == "blog":
            return analyze_blog(self, url, html, headers, page_type, level1)

        return analyze_general(self, url, html, headers, page_type, level1)
