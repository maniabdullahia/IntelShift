from analyzers.base_analyzer import BaseAnalyzer

from analyzers.wix.homepage import analyze_homepage
from analyzers.wix.collection import analyze_wix_collection
from analyzers.wix.product import analyze_product
from analyzers.wix.general import analyze_general


class WixAnalyzer(BaseAnalyzer):
    platform_name = "Wix"

    def analyze(self, url, html, headers, page_type, level1):
        if page_type == "homepage":
            return analyze_homepage(self, url, html, headers, page_type, level1)

        if page_type == "product":
            return analyze_product(self, url, html, headers, page_type, level1)

        # No separate Wix blog extractor yet.
        if page_type == "blog":
            result = analyze_general(url, html)
            result["pageType"] = "blog"
            return result

        # STOP: general pages must NOT pass through the collection extractor.
        # A page already classified as "general" has no collection evidence.
        if page_type == "general":
            return analyze_general(url, html)

        # Collection / shop / category: try collection extractor first,
        # fall back to general if no products or ecommerce signals found.
        if page_type in ["collection", "shop", "category"]:
            collection_result = analyze_wix_collection(
                self,
                url,
                html,
                headers,
                page_type,
                level1
            )

            has_products = bool(collection_result.get("products"))
            has_ecommerce = collection_result.get("ecommerce", {}).get(
                "hasEcommerceSignals",
                False
            )

            if has_products or has_ecommerce:
                return collection_result

            return analyze_general(url, html)

        return analyze_general(url, html)
