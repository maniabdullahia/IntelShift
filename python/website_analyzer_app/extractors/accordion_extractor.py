"""
accordion_extractor.py
======================
Shared utility for extracting content from accordions, tabs, expandable
sections, and hidden product containers — regardless of platform.

Supports:
  - HTML5 native <details><summary> accordions
  - Bootstrap 4/5 accordions (.accordion-item / .accordion-button / .accordion-collapse)
  - Shopify collapsible tabs (.collapsible-content, [data-accordion], disclosure elements)
  - Generic tab panels ([role="tabpanel"], .tab-pane, .tabs__pane)
  - FAQ accordion patterns
  - WooCommerce / Elementor accordion widgets
  - Data-attribute-driven accordions (data-title, data-tab-title, aria-label)

Returns a list of dicts:  {"title": str, "content": str}
The caller maps the title to a section type (ingredients, benefits, etc.)
"""

import re
from bs4 import BeautifulSoup


def clean_text(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _get_heading_text(element):
    """Return the best title string for an accordion block."""
    # Dedicated heading tags first
    for tag in ["summary", "button", "h1", "h2", "h3", "h4", "h5", "h6"]:
        found = element.find(tag)
        if found:
            text = clean_text(found.get_text(" ", strip=True))
            if text:
                return text

    # Data attributes
    for attr in ["data-title", "data-tab-title", "data-label", "data-tab", "aria-label"]:
        val = element.get(attr)
        if val:
            return clean_text(val)

    # id attribute as last resort
    id_val = element.get("id", "")
    if id_val:
        return clean_text(id_val.replace("-", " ").replace("_", " ").title())

    return None


def _get_content_text(element, heading_element=None):
    """Return the body text of an accordion block, stripping the heading."""
    clone = BeautifulSoup(str(element), "lxml")

    # Remove heading-like elements so they don't pollute the content
    for tag in clone.find_all(["summary", "button", "h1", "h2", "h3", "h4", "h5", "h6"]):
        tag.decompose()

    text = clean_text(clone.get_text(" ", strip=True))
    return text if len(text) >= 10 else None


def _get_list_items(element):
    """Extract list items from a block (used for bullets-style content)."""
    items = []
    clone = BeautifulSoup(str(element), "lxml")

    for tag in clone.find_all(["summary", "button", "h1", "h2", "h3", "h4"]):
        tag.decompose()

    for li in clone.find_all("li"):
        text = clean_text(li.get_text(" ", strip=True))
        if text and len(text) >= 5:
            items.append(text)

    return items


def _build_entry(title, element):
    """Build an accordion entry dict from a title and a BeautifulSoup element."""
    if not title:
        return None

    content_text = _get_content_text(element)
    list_items = _get_list_items(element)

    if not content_text and not list_items:
        return None

    return {
        "title": title,
        "content": content_text,
        "items": list_items,
    }


# ---------------------------------------------------------------------------
# Strategy 1: HTML5 <details><summary>
# ---------------------------------------------------------------------------

def _extract_details_summaries(soup):
    results = []
    for details in soup.find_all("details"):
        summary = details.find("summary")
        if not summary:
            continue
        title = clean_text(summary.get_text(" ", strip=True))
        entry = _build_entry(title, details)
        if entry:
            results.append(entry)
    return results


# ---------------------------------------------------------------------------
# Strategy 2: Bootstrap accordions
# ---------------------------------------------------------------------------

BOOTSTRAP_ACCORDION_SELECTORS = [
    ".accordion-item",
    ".accordion__item",
    "[class*='accordion-item']",
    "[class*='accordion__item']",
]

BOOTSTRAP_BUTTON_SELECTORS = [
    ".accordion-button",
    ".accordion__button",
    ".accordion-header button",
    "[class*='accordion-button']",
    "[class*='accordion__button']",
]

BOOTSTRAP_BODY_SELECTORS = [
    ".accordion-collapse",
    ".accordion-body",
    ".accordion__content",
    "[class*='accordion-body']",
    "[class*='accordion-collapse']",
    "[class*='accordion__content']",
]


def _extract_bootstrap_accordions(soup):
    results = []

    for selector in BOOTSTRAP_ACCORDION_SELECTORS:
        for item in soup.select(selector):
            # Title from button or heading
            title = None
            for btn_sel in BOOTSTRAP_BUTTON_SELECTORS:
                btn = item.select_one(btn_sel)
                if btn:
                    title = clean_text(btn.get_text(" ", strip=True))
                    break

            if not title:
                title = _get_heading_text(item)

            if not title:
                continue

            # Body from collapse/body container
            body = None
            for body_sel in BOOTSTRAP_BODY_SELECTORS:
                body = item.select_one(body_sel)
                if body:
                    break

            if not body:
                body = item  # fall back to whole item

            entry = _build_entry(title, body)
            if entry:
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Strategy 3: Shopify-specific collapsible / disclosure patterns
# ---------------------------------------------------------------------------

SHOPIFY_COLLAPSIBLE_SELECTORS = [
    ".collapsible-content",
    ".collapsible-content__inner",
    ".product__accordion",
    ".product__tab-content",
    ".product-accordion",
    "[data-accordion-content]",
    "[data-collapsible-content]",
    "[class*='collapsible-content']",
    "[class*='product__accordion']",
    ".disclosure__list-item",
    ".disclosure__panel",
]

SHOPIFY_PARENT_SELECTORS = [
    ".collapsible",
    "[data-accordion]",
    ".product__accordion-item",
    "[class*='collapsible-item']",
    "[class*='accordion-item']",
    ".disclosure",
]


def _extract_shopify_collapsibles(soup):
    results = []

    # Try parent-child approach first
    for parent_sel in SHOPIFY_PARENT_SELECTORS:
        for parent in soup.select(parent_sel):
            title = _get_heading_text(parent)
            if not title:
                continue
            # Find content within
            content_el = None
            for body_sel in SHOPIFY_COLLAPSIBLE_SELECTORS:
                content_el = parent.select_one(body_sel)
                if content_el:
                    break
            if not content_el:
                content_el = parent
            entry = _build_entry(title, content_el)
            if entry:
                results.append(entry)

    # Standalone content blocks with data attributes
    for sel in SHOPIFY_COLLAPSIBLE_SELECTORS:
        for block in soup.select(sel):
            title = _get_heading_text(block)
            if not title:
                # Check siblings for a title
                prev = block.find_previous_sibling()
                if prev:
                    title = clean_text(prev.get_text(" ", strip=True))
                    # Only keep it if it looks like a heading (short)
                    if title and len(title) > 80:
                        title = None
            if not title:
                continue
            entry = _build_entry(title, block)
            if entry:
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Strategy 4: Role-based tab panels
# ---------------------------------------------------------------------------

def _extract_tabpanels(soup):
    results = []

    for panel in soup.find_all(attrs={"role": "tabpanel"}):
        panel_id = panel.get("id") or panel.get("aria-labelledby")
        title = None

        # Find matching tab button/label
        if panel_id:
            tab = (
                soup.find(attrs={"aria-controls": panel_id})
                or soup.find(attrs={"data-target": f"#{panel_id}"})
                or soup.find(attrs={"href": f"#{panel_id}"})
            )
            if tab:
                title = clean_text(tab.get_text(" ", strip=True))

        if not title:
            title = _get_heading_text(panel)

        if not title:
            continue

        entry = _build_entry(title, panel)
        if entry:
            results.append(entry)

    # Also handle .tab-pane / .tabs__pane
    for sel in [".tab-pane", ".tabs__pane", "[class*='tab-pane']", "[class*='tabs__pane']"]:
        for pane in soup.select(sel):
            title = _get_heading_text(pane)
            if not title:
                # Look for a matching nav item by id
                pane_id = pane.get("id")
                if pane_id:
                    nav_link = soup.select_one(f"[href='#{pane_id}'], [data-target='#{pane_id}'], [data-bs-target='#{pane_id}']")
                    if nav_link:
                        title = clean_text(nav_link.get_text(" ", strip=True))
            if not title:
                continue
            entry = _build_entry(title, pane)
            if entry:
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Strategy 5: Elementor / page-builder accordion widgets
# ---------------------------------------------------------------------------

ELEMENTOR_ACCORDION_SELECTORS = [
    ".elementor-accordion-item",
    ".elementor-toggle-item",
    "[class*='elementor-accordion-item']",
]

ELEMENTOR_TITLE_SELECTORS = [
    ".elementor-accordion-title",
    ".elementor-toggle-title",
    "[class*='accordion-title']",
]

ELEMENTOR_CONTENT_SELECTORS = [
    ".elementor-accordion-content",
    ".elementor-toggle-content",
    "[class*='accordion-content']",
]


def _extract_elementor_accordions(soup):
    results = []

    for sel in ELEMENTOR_ACCORDION_SELECTORS:
        for item in soup.select(sel):
            title = None
            for t_sel in ELEMENTOR_TITLE_SELECTORS:
                t = item.select_one(t_sel)
                if t:
                    title = clean_text(t.get_text(" ", strip=True))
                    break
            if not title:
                title = _get_heading_text(item)
            if not title:
                continue

            content = None
            for c_sel in ELEMENTOR_CONTENT_SELECTORS:
                c = item.select_one(c_sel)
                if c:
                    content = c
                    break
            if not content:
                content = item

            entry = _build_entry(title, content)
            if entry:
                results.append(entry)

    return results


# ---------------------------------------------------------------------------
# Strategy 6: Generic heading + sibling content pattern
# Catches custom one-off accordion implementations.
# ---------------------------------------------------------------------------

GENERIC_HEADING_SELECTORS = [
    ".product-description [class*='section']",
    ".product__description [class*='section']",
    ".rte > h2",
    ".rte > h3",
    ".rte > h4",
    "[class*='product-info'] h3",
    "[class*='product-info'] h4",
    ".product-details h3",
    ".product-details h4",
]

# Only try this on section keywords to avoid pulling in nav / footer headings
SECTION_HEADING_KEYWORDS = [
    "ingredient", "benefit", "how to", "direction", "usage", "instruction",
    "feature", "highlight", "specification", "detail", "about", "faq",
    "question", "result", "why", "what", "key", "active", "formula",
    "description", "composition", "apply", "use", "size", "weight", "volume",
]


def _text_looks_like_section_heading(text):
    t = text.lower().strip()
    return any(kw in t for kw in SECTION_HEADING_KEYWORDS) and len(t) <= 100


def _extract_generic_heading_siblings(soup):
    results = []

    for sel in GENERIC_HEADING_SELECTORS:
        for heading in soup.select(sel):
            title = clean_text(heading.get_text(" ", strip=True))
            if not title or not _text_looks_like_section_heading(title):
                continue

            # Collect sibling content until next heading
            content_parts = []
            list_items_found = []
            sibling = heading.find_next_sibling()

            while sibling:
                tag = sibling.name if hasattr(sibling, "name") else None
                if tag in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    break
                if tag == "ul" or tag == "ol":
                    for li in sibling.find_all("li"):
                        item = clean_text(li.get_text(" ", strip=True))
                        if item:
                            list_items_found.append(item)
                else:
                    text = clean_text(sibling.get_text(" ", strip=True)) if tag else ""
                    if text:
                        content_parts.append(text)
                sibling = sibling.find_next_sibling()

            content_text = " ".join(content_parts).strip() or None
            if not content_text and not list_items_found:
                continue

            results.append({
                "title": title,
                "content": content_text,
                "items": list_items_found,
            })

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def extract_accordions(soup_or_html):
    """
    Extract accordion/tab/expandable section content from a page.

    Parameters
    ----------
    soup_or_html : BeautifulSoup | str
        Parsed soup object or raw HTML string.

    Returns
    -------
    list of dict
        [{"title": str, "content": str | None, "items": list[str]}, ...]

        `content` is the full text of the section.
        `items`   is a list of bullet/list items found inside (may be empty).
    """
    if isinstance(soup_or_html, str):
        soup = BeautifulSoup(soup_or_html, "lxml")
    else:
        soup = soup_or_html

    all_entries = []
    seen_titles = set()

    strategies = [
        _extract_details_summaries,
        _extract_bootstrap_accordions,
        _extract_shopify_collapsibles,
        _extract_tabpanels,
        _extract_elementor_accordions,
        _extract_generic_heading_siblings,
    ]

    for strategy in strategies:
        try:
            entries = strategy(soup)
        except Exception:
            entries = []

        for entry in entries:
            title_key = (entry.get("title") or "").lower().strip()
            if not title_key or title_key in seen_titles:
                continue
            # Skip very noisy / short titles that are clearly navigation
            if len(title_key) < 3 or len(title_key) > 120:
                continue
            seen_titles.add(title_key)
            all_entries.append(entry)

    return all_entries
