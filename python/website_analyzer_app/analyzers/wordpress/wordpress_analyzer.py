from analyzers.base_analyzer import BaseAnalyzer

from analyzers.wordpress.homepage import analyze_homepage
from analyzers.wordpress.collection import analyze_collection, is_woocommerce_collection_page
from analyzers.wordpress.product import analyze_product
from analyzers.wordpress.blog import analyze_blog
from analyzers.wordpress.general import analyze_general


class WordPressAnalyzer(BaseAnalyzer):
    platform_name = "WordPress / WooCommerce"

    def analyze(self, url, html, headers, page_type, level1):
        # Issue 1: honour Level-1 platform as source of truth.
        # Level-1 only promotes to "WooCommerce / WordPress" when it finds
        # definitive WooCommerce signals (woocommerce JS, wc-cart-fragments, etc.).
        # A pure WordPress site must not be silently upgraded to WooCommerce here.
        level1_platform = (level1 or {}).get("platform", "")
        if level1_platform == "WordPress":
            self.platform_name = "WordPress"
        elif level1_platform in ("WooCommerce / WordPress", "WordPress / WooCommerce"):
            self.platform_name = "WordPress / WooCommerce"
        # else: keep the class-level default for unknown/edge states

        page_type = (page_type or "general").lower().strip()

        # WooCommerce product-category priority override: pages that were
        # classified as something other than "collection"/"product" but show
        # clear WooCommerce category signals (e.g. /product-category/ URLs,
        # wp/v2/product_cat Link header, "Showing all X results", or repeated
        # "View Product" CTAs) are routed to the collection extractor instead.
        if page_type not in ("collection", "product"):
            try:
                if is_woocommerce_collection_page(url, html, headers):
                    page_type = "collection"
            except Exception:
                pass

        route_map = {
            "homepage": analyze_homepage,
            "collection": analyze_collection,
            "product": analyze_product,
            "blog": analyze_blog,
            "general": analyze_general,
            "other": analyze_general,
        }

        analyzer = route_map.get(page_type, analyze_general)

        return analyzer(
            self,
            url,
            html,
            headers,
            page_type,
            level1
        )
