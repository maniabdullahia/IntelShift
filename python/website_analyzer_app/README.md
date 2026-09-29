# Website Intelligence Analyzer

This is a starter Python project for detecting:

1. Website platform: Shopify, WordPress, WooCommerce, Wix, Next.js, React, Vue, Webflow, Magento, Unknown
2. Page type: homepage, collection/category, product, blog/article, general page
3. Structured JSON output based on platform and page type

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python main.py https://sivanna.com.pk/collections/foundation
```

The output JSON will be saved inside the `output/` folder.

## Project Flow

```text
URL
 ↓
Level 1 Detector
 ↓
Platform + Page Type
 ↓
Correct Platform Analyzer
 ↓
Correct Page-Type Extractor
 ↓
Normalized JSON Output
```

## Next Step

Train each analyzer using 10–20 website URLs per platform/page type.
