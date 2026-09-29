export const collectionPageSchema = {
    "page": {
        "url": "https://sivanna.com.pk/collections/foundation",
        "pageType": "ecommerce_collection",
        "title": "…",
        "metaDescription": null,
        "h1": "…",
        "collectionName": "Foundation",
        "collectionDescription": null
    },
    "productStats": {
        "currency": "PKR",
        "productCount": 24,
        "priceRange": { "min": 599, "max": 2499 },
        "inStockCount": null,
        "outOfStockCount": null,
        "hasFilters": true,
        "hasSort": true
    },
    "products": [
        {
            "rank": 1,
            "name": "…",
            "handle": null,
            "productUrl": "…",
            "imageUrl": "…",
            "additionalImageUrls": [],
            "price": {
                "currency": "PKR",
                "current": 1299,
                "compareAt": 1499,
                "isOnSale": true,
                "priceTextRaw": "Rs. 1,299.00"
            },
            "availability": {
                "status": "unknown",
                "inStock": null,
                "stockTextRaw": null
            },
            "category": "foundation",
            "vendor": null,
            "shortDescription": null,
            "swatches": [],
            "badges": ["sale"],
            "variants": [],
            "source": { "cardSelector": ".product-card:nth-child(1)", "confidence": 0.86 }
        }
    ],
}

export const productSchema = {
    name: "Products",
    description: "Schema for extracting product information from a web page.",
    fields: {
        page: {
            url: "string",
            pageType: "string",
            title: "string",
            imageUrl: "string",
            additionalImageUrls: ["string"],
            videoUrl: ["string"],
            metaDescription: "string",
            h1: "string",
            collectionName: "string",
            collectionDescription: "string",
        },
        price: {
            currency: "string",
            current: "number",
            compareAt: "number",
            isOnSale: "boolean",
            priceTextRaw: "string",
        },
        availability: {
            status: "string",
            inStock: "boolean",
            stockTextRaw: "string",
        },
        category: "string",
        vendor: "string",
        details: ["string"],
        swatches: [
            {
                name: "string",
                imageUrl: "string",
                colorHex: "string",
                isAvailable: "boolean",
            },
        ],
        productStats: {
            currency: "string",
            productCount: "number",
            price: "number",
            inStockCount: "number",
            outOfStockCount: "number",
            hasFilters: "boolean",
            hasSort: "boolean",
        },
        reviews: {
            averageRating: "number",
            reviewCount: "number",
        },
        productContent: {
            benefits: ["string"],
            ingredients: ["string"],
            usageInstructions: ["string"],
            safetyInstructions: ["string"],
            warnings: ["string"],
            certifications: ["string"],
        },
        youMayAlsoLike: [
            {
                title: "string",
                url: "string",
                imageUrl: "string",
                price: "number",
            },
        ],
    },
};

export const HomePageSchema = {
    storeInfo: {
        storeName: "",
        tagline: "",
        description: "",
        logoUrl: "",
        currency: "",
        language: ""
    },
    heroSection: {
        headline: "",
        subHeadline: "",
        ctaButtons: [
            {
                text: "",
                url: ""
            }
        ],
        backgroundImage: ""
    },
    topSellers: {
        title: "Top Sellers",
        products: [
            {
                name: "",
                url: "",
                image: "",
                price: "",
                originalPrice: "",
                discountPercentage: "",
                rating: "",
                reviewCount: "",
                badge: ""
            }
        ]
    },
    newArrivals: {
        title: "New Arrivals",
        products: []
    },
    featuredProducts: {
        title: "",
        products: []
    },
    featuredCategories: [
        {
            name: "",
            url: "",
            image: "",
            productCount: ""
        }
    ],
    topCollections: [
        {
            name: "",
            url: "",
            description: ""
        }
    ],
    deals: {
        title: "",
        products: [],
        endDate: ""
    },
    onSale: {
        title: "On Sale",
        products: []
    },
    recommendations: {
        title: "",
        products: [],
        basedOn: "trending | recently_viewed | personalized | popular"
    },
    reviewsSummary: {
        averageRating: "",
        totalReviews: "",
        highlightReviews: [
            {
                author: "",
                rating: "",
                comment: ""
            }
        ]
    },
    aboutUs: {
        title: "",
        content: "",
        image: ""
    },
    websiteFeatures: [
        {
            title: "",
            description: "",
            icon: ""
        }
    ],
    trustSignals: [
        {
            type: "payment | security | certification | guarantee",
            label: "",
            image: ""
        }
    ],
    contactInfo: {
        email: "",
        phone: "",
        address: "",
        socialLinks: {
            facebook: "",
            instagram: "",
            twitter: "",
            linkedin: "",
            youtube: ""
        }
    },
    navigation: {
        mainMenu: [
            {
                label: "",
                url: ""
            }
        ],
        footerMenu: [
            {
                label: "",
                url: ""
            }
        ]
    },
    searchEnabled: true,
    newsletterSignup: {
        enabled: true,
        incentive: ""
    },
    metadata: {
        pageTitle: "",
        metaDescription: "",
        canonicalUrl: ""
    }
}

export const UniversalAnalyticsSchema = {

    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://schemas.example.com/universal-analysis-report/v1",
    "title": "Universal Analysis Report",
    "description": "A domain-agnostic schema for structured analytical reports. Supports competitive intelligence, product comparisons, market research, scientific studies, financial analysis, and any multi-subject evaluation. Inspired by the Hubble vs Kensington Office Group competitive analysis.",
    "type": "object",
    "required": ["meta", "subjects"],

    "definitions": {

        "scalar_value": {
            "$id": "#scalar_value",
            "description": "A flexible value cell that can represent any data type as a display string, with optional raw numeric form and null handling.",
            "type": "object",
            "required": ["display"],
            "properties": {
                "display": { "type": "string", "description": "Human-readable formatted value", "examples": ["499+", "4.9 / 5", "$1,200/mo", "N/A"] },
                "raw": { "type": ["number", "string", "boolean", "null"], "description": "Machine-readable raw value for sorting/computation" },
                "unit": { "type": "string", "description": "Unit of measurement", "examples": ["%", "USD", "/5", "ms", "km²"] },
                "is_null": { "type": "boolean", "default": false, "description": "True when data is absent, unknown, or not applicable" },
                "null_reason": { "type": "string", "description": "Why the value is absent", "examples": ["Not stated", "Not applicable", "Data unavailable"] },
                "confidence": { "type": "string", "enum": ["verified", "estimated", "inferred", "unknown"], "default": "verified" },
                "as_of": { "type": "string", "format": "date", "description": "Date this value was current" },
                "source": { "type": "string", "description": "Where this value came from", "examples": ["Annual report 2024", "Company website", "Third-party audit"] }
            }
        },

        "subject_ref": {
            "$id": "#subject_ref",
            "description": "A reference to one subject (entity/series/category) in the subjects array.",
            "type": "object",
            "required": ["subject_id"],
            "properties": {
                "subject_id": { "type": "string", "description": "Must match a subject.id in the subjects array" },
                "value": { "$ref": "#scalar_value" }
            }
        },

        "dataset": {
            "$id": "#dataset",
            "description": "A generic, chart-ready dataset. Can be subject-scoped or standalone.",
            "type": "object",
            "required": ["series"],
            "properties": {
                "labels": { "type": "array", "items": { "type": "string" }, "description": "X-axis or category labels shared across all series" },
                "series": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "required": ["label", "data"],
                        "properties": {
                            "label": { "type": "string", "description": "Series display name. May reference a subject name or be freeform." },
                            "subject_id": { "type": "string", "description": "Optional link to a subject. Omit for standalone series." },
                            "data": {
                                "description": "Series data — supports flat numbers, key-value pairs, or point objects (x/y/r/z).",
                                "oneOf": [
                                    {
                                        "type": "array",
                                        "items": { "type": ["number", "null"] },
                                        "description": "Flat numeric array aligned to labels"
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["x", "y"],
                                            "properties": {
                                                "x": { "type": ["number", "string"] },
                                                "y": { "type": "number" },
                                                "r": { "type": "number", "description": "Bubble radius" },
                                                "z": { "type": "number", "description": "Fourth dimension / heat value" },
                                                "label": { "type": "string" }
                                            }
                                        },
                                        "description": "Point objects for scatter, bubble, or multi-dimensional charts"
                                    },
                                    {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["key", "value"],
                                            "properties": {
                                                "key": { "type": "string" },
                                                "value": { "type": ["number", "null"] }
                                            }
                                        },
                                        "description": "Key-value pairs for named data points"
                                    }
                                ]
                            },
                            "color": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
                            "stack_group": { "type": "string", "description": "Group key for stacked charts" }
                        }
                    }
                },
                "x_axis": {
                    "type": "object",
                    "properties": {
                        "label": { "type": "string" },
                        "type": { "type": "string", "enum": ["category", "linear", "logarithmic", "time", "radial"] },
                        "min": { "type": "number" },
                        "max": { "type": "number" }
                    }
                },
                "y_axis": {
                    "type": "object",
                    "properties": {
                        "label": { "type": "string" },
                        "type": { "type": "string", "enum": ["category", "linear", "logarithmic", "time", "radial"] },
                        "min": { "type": "number" },
                        "max": { "type": "number" }
                    }
                }
            }
        },

        "visualization_block": {
            "$id": "#visualization_block",
            "description": "A self-contained chart or visual module that can appear anywhere in the report.",
            "type": "object",
            "required": ["type", "title"],
            "properties": {
                "id": { "type": "string" },
                "type": {
                    "type": "string",
                    "enum": [
                        "summary", "detailed", "table", "list", "comparison", "insights",
                        "recommendations", "visualization", "trends", "highlights",
                        "key_metrics", "side_by_side", "swot_analysis", "competitive_matrix",
                        "heatmap", "timeline", "infographic", "dashboard",
                        "bar_chart", "pie_chart", "line_graph", "scatter_plot",
                        "word_cloud", "network_graph", "geographical_map",
                        "sentiment_analysis", "customer_journey_map", "funnel_analysis",
                        "cohort_analysis", "correlation_matrix", "regression_analysis",
                        "cluster_analysis", "anomaly_detection", "forecasting",
                        "scenario_analysis", "what_if_analysis", "data_storytelling",
                        "interactive_report", "custom_visualization"
                    ]
                },
                "title": { "type": "string" },
                "subtitle": { "type": "string" },
                "description": { "type": "string" },
                "dataset": { "$ref": "#dataset" },
                "config": {
                    "type": "object",
                    "description": "Renderer-specific options (e.g. stacked, orientation, color palette)",
                    "additionalProperties": true
                }
            }
        },

        "attribute_row": {
            "$id": "#attribute_row",
            "description": "A single labeled row with per-subject values — the core unit of comparison tables.",
            "type": "object",
            "required": ["label", "subject_values"],
            "properties": {
                "label": { "type": "string", "description": "Row label / dimension name", "examples": ["Core claim", "Pricing model", "Market share"] },
                "category": { "type": "string", "description": "Optional grouping category for the row" },
                "subject_values": {
                    "type": "array",
                    "items": { "$ref": "#subject_ref" },
                    "description": "One entry per subject"
                },
                "winner": {
                    "description": "Which subject leads on this dimension. Can be a subject_id, 'tie', or null if not applicable.",
                    "oneOf": [
                        { "type": "string" },
                        { "type": "null" }
                    ]
                },
                "weight": { "type": "number", "minimum": 0, "maximum": 1, "description": "Relative importance of this dimension (for weighted scoring)" },
                "notes": { "type": "string" }
            }
        },

        "recommendation_item": {
            "$id": "#recommendation_item",
            "description": "A single prioritised action item.",
            "type": "object",
            "required": ["action", "expected_impact"],
            "properties": {
                "priority": { "type": "string", "enum": ["critical", "high", "medium", "low"] },
                "action": { "type": "string" },
                "expected_impact": { "type": "string" },
                "effort": { "type": "string", "enum": ["low", "medium", "high"] },
                "category": { "type": "string", "description": "Freeform category tag", "examples": ["SEO", "UX", "pricing", "trust", "product", "compliance"] },
                "time_horizon": { "type": "string", "examples": ["0–30 days", "Q3 2025", "12–18 months"] },
                "kpi": { "type": "string", "description": "The metric this action is expected to move", "examples": ["Conversion rate", "Organic traffic", "NPS"] }
            }
        },

        "swot_quadrant": {
            "$id": "#swot_quadrant",
            "description": "A SWOT analysis for one subject.",
            "type": "object",
            "required": ["subject_id"],
            "properties": {
                "subject_id": { "type": "string" },
                "strengths": { "type": "array", "items": { "type": "string" } },
                "weaknesses": { "type": "array", "items": { "type": "string" } },
                "opportunities": { "type": "array", "items": { "type": "string" } },
                "threats": { "type": "array", "items": { "type": "string" } }
            }
        },

        "insight_card": {
            "$id": "#insight_card",
            "description": "A single strategic or analytical insight.",
            "type": "object",
            "required": ["title", "body"],
            "properties": {
                "theme": { "type": "string", "description": "Short theme label", "examples": ["Conversion strategy", "Trust building", "Market dynamics"] },
                "title": { "type": "string" },
                "body": { "type": "string" },
                "subjects_mentioned": { "type": "array", "items": { "type": "string" }, "description": "subject_ids referenced in this insight" },
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "summary", "detailed", "table", "list", "comparison", "insights",
                            "recommendations", "visualization", "trends", "highlights",
                            "key_metrics", "side_by_side", "swot_analysis", "competitive_matrix",
                            "heatmap", "timeline", "infographic", "dashboard",
                            "bar_chart", "pie_chart", "line_graph", "scatter_plot",
                            "word_cloud", "network_graph", "geographical_map",
                            "sentiment_analysis", "customer_journey_map", "funnel_analysis",
                            "cohort_analysis", "correlation_matrix", "regression_analysis",
                            "cluster_analysis", "anomaly_detection", "forecasting",
                            "scenario_analysis", "what_if_analysis", "data_storytelling",
                            "interactive_report", "custom_visualization"
                        ]
                    }
                },
                "severity": { "type": "string", "enum": ["info", "warning", "critical", "opportunity"] },
                "confidence": { "type": "string", "enum": ["high", "medium", "low", "speculative"] }
            }
        }

    },

    "properties": {

        "meta": {
            "type": "object",
            "description": "Report-level metadata. Domain-agnostic — works for any industry, use case, or data type.",
            "required": ["title", "report_type"],
            "properties": {
                "title": { "type": "string", "description": "Report headline", "examples": ["Hubble vs Kensington", "Q3 Performance Review", "EV Battery Tech Landscape 2025"] },
                "subtitle": { "type": "string" },
                "kicker": { "type": "string", "description": "Eyebrow / context line above the title", "examples": ["Competitive Intelligence · 2025", "Internal · Confidential"] },
                "description": { "type": "string", "description": "Long-form abstract or report summary" },
                "report_type": {
                    "type": "string",
                    "enum": [
                        "summary", "detailed", "comparison", "dashboard",
                        "data_storytelling", "interactive_report", "infographic",
                        "research", "audit", "forecast", "custom"
                    ]
                },
                "context": {
                    "type": "object",
                    "description": "Freeform domain context — replaces hardcoded industry/market fields.",
                    "additionalProperties": { "type": "string" },
                    "examples": [
                        { "industry": "UK Flexible Workspace", "market": "London", "scope": "Two-brand competitive deep-dive" },
                        { "department": "Product", "quarter": "Q3 2025", "objective": "Pricing strategy review" },
                        { "domain": "Immunology", "study_type": "Meta-analysis", "population": "Adults 18–65" }
                    ]
                },
                "date_range": {
                    "type": "object",
                    "properties": {
                        "from": { "type": "string", "format": "date" },
                        "to": { "type": "string", "format": "date" }
                    }
                },
                "authored_by": { "type": "string" },
                "version": { "type": "string", "examples": ["1.0.0", "draft-2"] },
                "tags": { "type": "array", "items": { "type": "string" } },
                "sections": {
                    "type": "array",
                    "description": "Ordered navigation / table-of-contents for the report.",
                    "items": {
                        "type": "object",
                        "required": ["id", "label"],
                        "properties": {
                            "id": { "type": "string" },
                            "label": { "type": "string" },
                            "order": { "type": "integer" },
                            "icon": { "type": "string" }
                        }
                    }
                }
            }
        },

        "subjects": {
            "type": "array",
            "description": "The entities, items, or series being analysed or compared. Can be brands, products, countries, time periods, cohorts, experiments, categories — anything.",
            "minItems": 1,
            "items": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": { "type": "string", "description": "Unique key referenced throughout the report", "examples": ["hub", "kog", "product_a", "2024_q1", "control_group"] },
                    "name": { "type": "string", "examples": ["Hubble", "Kensington Office Group", "Product A", "Q1 2024", "Control"] },
                    "short_name": { "type": "string", "description": "Abbreviated label for charts and tight spaces" },
                    "descriptor": { "type": "string", "description": "One-phrase description of what this subject is", "examples": ["Marketplace", "Premium operator", "Baseline cohort"] },
                    "role": {
                        "type": "string",
                        "description": "This subject's analytical role. Freeform to support any domain.",
                        "examples": ["primary", "competitor", "benchmark", "control", "treatment", "reference", "challenger", "market_leader", "niche_player", "custom"]
                    },
                    "color_hex": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
                    "url": { "type": "string", "format": "uri", "description": "Optional — only relevant for web-based subjects" },
                    "attributes": {
                        "type": "object",
                        "description": "Arbitrary key-value metadata for this subject. Fully freeform.",
                        "additionalProperties": true,
                        "examples": [
                            { "founded": "1991", "hq": "London", "model": "Direct operator" },
                            { "genome": "BRCA1", "condition": "Triple-negative breast cancer" },
                            { "sku": "PRD-4421", "category": "Electronics", "price_usd": 299 }
                        ]
                    }
                }
            }
        },

        "sections": {
            "type": "array",
            "description": "The ordered body of the report. Each section is a named block with a type, optional subjects scope, and one or more content blocks.",
            "items": {
                "type": "object",
                "required": ["id", "type", "title"],
                "properties": {
                    "id": { "type": "string" },
                    "order": { "type": "integer" },
                    "type": {
                        "type": "string",
                        "enum": [
                            "summary", "detailed", "table", "list", "comparison", "insights",
                            "recommendations", "visualization", "trends", "highlights",
                            "key_metrics", "side_by_side", "swot_analysis", "competitive_matrix",
                            "heatmap", "timeline", "infographic", "dashboard",
                            "bar_chart", "pie_chart", "line_graph", "scatter_plot",
                            "word_cloud", "network_graph", "geographical_map",
                            "sentiment_analysis", "customer_journey_map", "funnel_analysis",
                            "cohort_analysis", "correlation_matrix", "regression_analysis",
                            "cluster_analysis", "anomaly_detection", "forecasting",
                            "scenario_analysis", "what_if_analysis", "data_storytelling",
                            "interactive_report", "custom_visualization"
                        ]
                    },
                    "title": { "type": "string" },
                    "subtitle": { "type": "string" },
                    "description": { "type": "string" },
                    "subject_scope": {
                        "type": "array",
                        "items": { "type": "string" },
                        "description": "Optional subset of subject_ids this section focuses on. Omit to mean 'all subjects'."
                    },
                    "content": {
                        "type": "object",
                        "description": "Section payload. Only the fields relevant to the section type need to be populated.",
                        "properties": {

                            "metric_strip": {
                                "type": "array",
                                "description": "Row of top-line KPIs, each with per-subject values. Use for key_metrics and summary sections.",
                                "items": {
                                    "type": "object",
                                    "required": ["label", "subject_values"],
                                    "properties": {
                                        "label": { "type": "string" },
                                        "icon": { "type": "string" },
                                        "subject_values": { "type": "array", "items": { "$ref": "#subject_ref" } }
                                    }
                                }
                            },

                            "scorecards": {
                                "type": "array",
                                "description": "Profile card per subject with a tagline and a list of stats.",
                                "items": {
                                    "type": "object",
                                    "required": ["subject_id"],
                                    "properties": {
                                        "subject_id": { "type": "string" },
                                        "tagline": { "type": "string" },
                                        "image_url": { "type": "string", "format": "uri" },
                                        "stats": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["label", "value"],
                                                "properties": {
                                                    "label": { "type": "string" },
                                                    "value": { "$ref": "#scalar_value" }
                                                }
                                            }
                                        },
                                        "narrative": { "type": "string" }
                                    }
                                }
                            },

                            "attribute_table": {
                                "type": "array",
                                "description": "Structured comparison table. Each row is one dimension; columns are subjects. Use for side_by_side, table, comparison, competitive_matrix.",
                                "items": { "$ref": "#attribute_row" }
                            },

                            "overlap": {
                                "type": "object",
                                "description": "Venn-style overlap across N subjects. Keys are subject_ids; 'shared' is the intersection.",
                                "properties": {
                                    "shared": { "type": "array", "items": { "type": "string" }, "description": "Items common to all scoped subjects" },
                                    "exclusive": {
                                        "type": "array",
                                        "description": "Items belonging exclusively to one subject",
                                        "items": {
                                            "type": "object",
                                            "required": ["subject_id", "items"],
                                            "properties": {
                                                "subject_id": { "type": "string" },
                                                "items": { "type": "array", "items": { "type": "string" } }
                                            }
                                        }
                                    },
                                    "partial": {
                                        "type": "array",
                                        "description": "Items shared by some but not all subjects",
                                        "items": {
                                            "type": "object",
                                            "required": ["subject_ids", "items"],
                                            "properties": {
                                                "subject_ids": { "type": "array", "items": { "type": "string" } },
                                                "items": { "type": "array", "items": { "type": "string" } }
                                            }
                                        }
                                    }
                                }
                            },

                            "swot": {
                                "type": "array",
                                "description": "One SWOT quadrant per subject. Use for swot_analysis sections.",
                                "items": { "$ref": "#swot_quadrant" }
                            },

                            "insights": {
                                "type": "array",
                                "description": "Strategic or analytical insight cards.",
                                "items": { "$ref": "#insight_card" }
                            },

                            "recommendations": {
                                "type": "array",
                                "description": "Prioritised action items, optionally scoped to a subject.",
                                "items": {
                                    "type": "object",
                                    "required": ["items"],
                                    "properties": {
                                        "subject_id": { "type": "string", "description": "Omit for report-wide recommendations" },
                                        "group_label": { "type": "string" },
                                        "items": { "type": "array", "items": { "$ref": "#recommendation_item" } }
                                    }
                                }
                            },

                            "charts": {
                                "type": "array",
                                "description": "One or more charts rendered inside this section.",
                                "items": { "$ref": "#visualization_block" }
                            },

                            "timeline": {
                                "type": "object",
                                "description": "Ordered sequence of events or milestones.",
                                "properties": {
                                    "events": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["date", "label"],
                                            "properties": {
                                                "date": { "type": "string" },
                                                "label": { "type": "string" },
                                                "body": { "type": "string" },
                                                "subject_id": { "type": "string" },
                                                "type": { "type": "string", "examples": ["milestone", "launch", "risk", "opportunity"] }
                                            }
                                        }
                                    }
                                }
                            },

                            "funnel": {
                                "type": "object",
                                "description": "Staged funnel with per-subject conversion or volume data.",
                                "properties": {
                                    "stages": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["stage"],
                                            "properties": {
                                                "stage": { "type": "string" },
                                                "description": { "type": "string" },
                                                "subject_values": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "required": ["subject_id"],
                                                        "properties": {
                                                            "subject_id": { "type": "string" },
                                                            "value": { "$ref": "#scalar_value" },
                                                            "conversion_rate": { "type": "number", "minimum": 0, "maximum": 1 },
                                                            "note": { "type": "string" }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },

                            "customer_journey": {
                                "type": "object",
                                "description": "Stage-by-stage journey map with touchpoints and per-subject performance.",
                                "properties": {
                                    "stages": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["stage"],
                                            "properties": {
                                                "stage": { "type": "string" },
                                                "description": { "type": "string" },
                                                "touchpoints": { "type": "array", "items": { "type": "string" } },
                                                "emotions": { "type": "array", "items": { "type": "string" } },
                                                "pain_points": { "type": "array", "items": { "type": "string" } },
                                                "subject_values": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "subject_id": { "type": "string" },
                                                            "score": { "type": "number" },
                                                            "note": { "type": "string" }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            },

                            "scenarios": {
                                "type": "array",
                                "description": "What-if or scenario analysis entries.",
                                "items": {
                                    "type": "object",
                                    "required": ["name", "description"],
                                    "properties": {
                                        "name": { "type": "string" },
                                        "description": { "type": "string" },
                                        "assumptions": { "type": "array", "items": { "type": "string" } },
                                        "subject_id": { "type": "string", "description": "Subject most affected" },
                                        "projected_outcome": { "type": "string" },
                                        "impact_score": { "type": "number" },
                                        "probability": { "type": "string", "enum": ["very_low", "low", "medium", "high", "very_high"] },
                                        "time_horizon": { "type": "string" }
                                    }
                                }
                            },

                            "heatmap": {
                                "type": "object",
                                "description": "2D intensity matrix. Rows and columns can be any categorical dimensions.",
                                "required": ["rows", "columns", "values"],
                                "properties": {
                                    "rows": { "type": "array", "items": { "type": "string" } },
                                    "columns": { "type": "array", "items": { "type": "string" } },
                                    "values": {
                                        "type": "array",
                                        "description": "Row-major 2D array of numbers (rows × columns)",
                                        "items": { "type": "array", "items": { "type": ["number", "null"] } }
                                    },
                                    "color_scale": { "type": "string", "enum": ["sequential", "diverging", "categorical"], "default": "sequential" },
                                    "value_unit": { "type": "string" }
                                }
                            },

                            "correlation_matrix": {
                                "type": "object",
                                "description": "Symmetric correlation coefficient matrix.",
                                "required": ["dimensions", "matrix"],
                                "properties": {
                                    "dimensions": { "type": "array", "items": { "type": "string" } },
                                    "matrix": {
                                        "type": "array",
                                        "items": { "type": "array", "items": { "type": "number", "minimum": -1, "maximum": 1 } }
                                    },
                                    "method": { "type": "string", "enum": ["pearson", "spearman", "kendall", "custom"], "default": "pearson" }
                                }
                            },

                            "network_graph": {
                                "type": "object",
                                "description": "Node-link graph for relationship or dependency visualisation.",
                                "required": ["nodes"],
                                "properties": {
                                    "nodes": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["id", "label"],
                                            "properties": {
                                                "id": { "type": "string" },
                                                "label": { "type": "string" },
                                                "type": { "type": "string" },
                                                "subject_id": { "type": "string" },
                                                "size": { "type": "number" },
                                                "color_hex": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" },
                                                "attributes": { "type": "object", "additionalProperties": true }
                                            }
                                        }
                                    },
                                    "edges": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["from", "to"],
                                            "properties": {
                                                "from": { "type": "string" },
                                                "to": { "type": "string" },
                                                "label": { "type": "string" },
                                                "weight": { "type": "number" },
                                                "directed": { "type": "boolean", "default": true },
                                                "type": { "type": "string" }
                                            }
                                        }
                                    },
                                    "layout": { "type": "string", "enum": ["force", "hierarchical", "circular", "radial", "custom"] }
                                }
                            },

                            "geographical_map": {
                                "type": "object",
                                "description": "Location-based data for map rendering. Coordinate system is WGS84.",
                                "properties": {
                                    "points": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["lat", "lng", "label"],
                                            "properties": {
                                                "lat": { "type": "number", "minimum": -90, "maximum": 90 },
                                                "lng": { "type": "number", "minimum": -180, "maximum": 180 },
                                                "label": { "type": "string" },
                                                "subject_id": { "type": "string" },
                                                "value": { "$ref": "#scalar_value" },
                                                "attributes": { "type": "object", "additionalProperties": true }
                                            }
                                        }
                                    },
                                    "regions": {
                                        "type": "array",
                                        "description": "Named administrative regions with an associated value.",
                                        "items": {
                                            "type": "object",
                                            "required": ["region_id", "label"],
                                            "properties": {
                                                "region_id": { "type": "string", "description": "ISO 3166-2 or custom region code" },
                                                "label": { "type": "string" },
                                                "subject_id": { "type": "string" },
                                                "value": { "$ref": "#scalar_value" }
                                            }
                                        }
                                    },
                                    "center": { "type": "object", "properties": { "lat": { "type": "number" }, "lng": { "type": "number" } } },
                                    "zoom": { "type": "number" }
                                }
                            },

                            "word_cloud": {
                                "type": "array",
                                "description": "One term-weight array per subject (or standalone if subject_id is omitted).",
                                "items": {
                                    "type": "object",
                                    "required": ["terms"],
                                    "properties": {
                                        "subject_id": { "type": "string" },
                                        "terms": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": ["word", "weight"],
                                                "properties": {
                                                    "word": { "type": "string" },
                                                    "weight": { "type": "number", "minimum": 0, "maximum": 1 },
                                                    "sentiment": { "type": "number", "minimum": -1, "maximum": 1 }
                                                }
                                            }
                                        }
                                    }
                                }
                            },

                            "cohort_analysis": {
                                "type": "object",
                                "description": "Retention or behaviour data grouped by cohort over time.",
                                "required": ["cohorts", "periods"],
                                "properties": {
                                    "metric": { "type": "string", "examples": ["Retention rate", "Revenue", "Churn"] },
                                    "cohorts": { "type": "array", "items": { "type": "string" } },
                                    "periods": { "type": "array", "items": { "type": "string" } },
                                    "values": {
                                        "type": "array",
                                        "description": "Row-major 2D array: cohorts × periods",
                                        "items": { "type": "array", "items": { "type": ["number", "null"] } }
                                    }
                                }
                            },

                            "forecasting": {
                                "type": "object",
                                "description": "Time-series forecast with actuals and projected values.",
                                "properties": {
                                    "metric": { "type": "string" },
                                    "series": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["subject_id", "actuals"],
                                            "properties": {
                                                "subject_id": { "type": "string" },
                                                "actuals": {
                                                    "type": "array",
                                                    "items": { "type": "object", "properties": { "period": { "type": "string" }, "value": { "type": "number" } } }
                                                },
                                                "forecast": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "period": { "type": "string" },
                                                            "value": { "type": "number" },
                                                            "lower_bound": { "type": "number" },
                                                            "upper_bound": { "type": "number" },
                                                            "confidence_pct": { "type": "number" }
                                                        }
                                                    }
                                                },
                                                "model": { "type": "string", "examples": ["ARIMA", "linear_regression", "exponential_smoothing"] }
                                            }
                                        }
                                    }
                                }
                            },

                            "sentiment_analysis": {
                                "type": "object",
                                "description": "Sentiment scoring across dimensions or time.",
                                "properties": {
                                    "subject_sentiments": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["subject_id"],
                                            "properties": {
                                                "subject_id": { "type": "string" },
                                                "overall": { "type": "number", "minimum": -1, "maximum": 1 },
                                                "positive_pct": { "type": "number" },
                                                "neutral_pct": { "type": "number" },
                                                "negative_pct": { "type": "number" },
                                                "by_dimension": {
                                                    "type": "array",
                                                    "items": {
                                                        "type": "object",
                                                        "properties": {
                                                            "dimension": { "type": "string" },
                                                            "score": { "type": "number", "minimum": -1, "maximum": 1 }
                                                        }
                                                    }
                                                },
                                                "sample_quotes": { "type": "array", "items": { "type": "string" } }
                                            }
                                        }
                                    }
                                }
                            },

                            "anomaly_detection": {
                                "type": "object",
                                "description": "Flagged anomalies or outliers in a dataset.",
                                "properties": {
                                    "anomalies": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["label", "description"],
                                            "properties": {
                                                "label": { "type": "string" },
                                                "description": { "type": "string" },
                                                "subject_id": { "type": "string" },
                                                "severity": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
                                                "detected_at": { "type": "string" },
                                                "value": { "$ref": "#scalar_value" },
                                                "expected": { "$ref": "#scalar_value" },
                                                "deviation": { "type": "number", "description": "Standard deviations from mean or expected" }
                                            }
                                        }
                                    }
                                }
                            },

                            "regression_analysis": {
                                "type": "object",
                                "description": "Regression model results.",
                                "properties": {
                                    "dependent_variable": { "type": "string" },
                                    "independent_variables": { "type": "array", "items": { "type": "string" } },
                                    "r_squared": { "type": "number", "minimum": 0, "maximum": 1 },
                                    "coefficients": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "properties": {
                                                "variable": { "type": "string" },
                                                "estimate": { "type": "number" },
                                                "std_error": { "type": "number" },
                                                "p_value": { "type": "number" },
                                                "significant": { "type": "boolean" }
                                            }
                                        }
                                    },
                                    "model_type": { "type": "string", "examples": ["OLS", "logistic", "ridge", "lasso"] }
                                }
                            },

                            "cluster_analysis": {
                                "type": "object",
                                "description": "Cluster membership for subjects or data points.",
                                "properties": {
                                    "algorithm": { "type": "string", "examples": ["k-means", "DBSCAN", "hierarchical"] },
                                    "clusters": {
                                        "type": "array",
                                        "items": {
                                            "type": "object",
                                            "required": ["cluster_id", "label"],
                                            "properties": {
                                                "cluster_id": { "type": "string" },
                                                "label": { "type": "string" },
                                                "description": { "type": "string" },
                                                "members": { "type": "array", "items": { "type": "string" }, "description": "subject_ids or data point IDs" },
                                                "centroid": { "type": "object", "additionalProperties": { "type": "number" } }
                                            }
                                        }
                                    }
                                }
                            },

                            "highlights": {
                                "type": "array",
                                "description": "Short bullet-point or card highlights for summary sections.",
                                "items": {
                                    "type": "object",
                                    "required": ["text"],
                                    "properties": {
                                        "text": { "type": "string" },
                                        "subject_id": { "type": "string" },
                                        "type": { "type": "string", "enum": ["positive", "negative", "neutral", "warning"] },
                                        "icon": { "type": "string" }
                                    }
                                }
                            },

                            "list": {
                                "type": "array",
                                "description": "Generic ordered or unordered list of items.",
                                "items": {
                                    "type": "object",
                                    "required": ["text"],
                                    "properties": {
                                        "text": { "type": "string" },
                                        "subject_id": { "type": "string" },
                                        "value": { "$ref": "#scalar_value" },
                                        "rank": { "type": "integer" }
                                    }
                                }
                            },

                            "narrative": {
                                "type": "string",
                                "description": "Freeform prose content for detailed or data_storytelling sections."
                            },

                            "custom": {
                                "type": "object",
                                "description": "Escape hatch for any domain-specific content not covered above.",
                                "additionalProperties": true
                            }

                        },
                        "additionalProperties": false
                    }
                }
            }
        },

        "report_config": {
            "type": "object",
            "description": "Rendering, theming, and export configuration. All fields optional.",
            "properties": {
                "layout": { "type": "string", "enum": ["sectioned", "dashboard", "single_page", "infographic", "print"] },
                "color_scheme": {
                    "type": "object",
                    "description": "Design token overrides",
                    "properties": {
                        "background": { "type": "string" },
                        "surface": { "type": "string" },
                        "border": { "type": "string" },
                        "text": { "type": "string" },
                        "muted": { "type": "string" },
                        "accent": { "type": "string" }
                    }
                },
                "fonts": {
                    "type": "object",
                    "properties": {
                        "display": { "type": "string" },
                        "body": { "type": "string" },
                        "mono": { "type": "string" }
                    }
                },
                "default_chart_palette": {
                    "type": "array",
                    "items": { "type": "string", "pattern": "^#[0-9A-Fa-f]{6}$" }
                },
                "locale": { "type": "string", "default": "en-GB", "description": "BCP 47 language tag for number/date formatting" },
                "currency": { "type": "string", "default": "GBP", "description": "ISO 4217 currency code" },
                "export_formats": { "type": "array", "items": { "type": "string", "enum": ["pdf", "png", "html", "json", "csv", "pptx"] } },
                "interactive": { "type": "boolean", "default": true },
                "show_data_sources": { "type": "boolean", "default": true }
            }
        },

        "data_sources": {
            "type": "array",
            "description": "Bibliography of data sources used throughout the report.",
            "items": {
                "type": "object",
                "required": ["id", "label"],
                "properties": {
                    "id": { "type": "string" },
                    "label": { "type": "string" },
                    "url": { "type": "string", "format": "uri" },
                    "accessed_on": { "type": "string", "format": "date" },
                    "type": { "type": "string", "enum": ["website", "api", "database", "document", "survey", "interview", "internal", "third_party"] },
                    "notes": { "type": "string" }
                }
            }
        }

    },

    "additionalProperties": false

}

// export const UniversalSchema = {
//     "analysis_identity": {
//         "competitors": ["string"],
//         "description": "string",
//         "tags": ["string"],
//     },
//     "executive_summary": {
//         "title": "string",
//         "subtitle": "string",
//         "key_findings": ["string"],
//         "recommendations": ["string"],
//     },
//     "feature_matrix": {
//         "title": "Feature Matrix",
//         "subtitle": "string",
//         "data":
//         {
//             "table": {
//                 "headers": ["string"],
//                 "rows": []
//             },
//             "visualization": {
//                 "type": "string",
//                 "data": [
//                     {}
//                 ]
//             }
//         }
//     },
//     "swot_analysis": {
//         "title": "SWOT Analysis",
//         "subtitle": "string",
//         "competitor": [
//             {
//                 "name": "string",
//                 "description": "string",
//                 "quadrants": {
//                     "strengths": ["string"],
//                     "weaknesses": ["string"],
//                     "opportunities": ["string"],
//                     "threats": ["string"],
//                 }
//             }
//         ],
//     },
//     "recommendations": {
//         "title": "Strategic Recommendations",
//         "subtitle": "string",
//         "competitor_specific": [
//             {
//                 "competitor": "string",
//                 "recommendations": [
//                     {
//                         "priority": "string",
//                         "action": "string",
//                         "impact": "string",
//                     }
//                 ]
//             }
//         ]
//     },
//     "key_insights": {
//         "title": "Key Insights",
//         "subtitle": "string",
//         "insights": [
//             {
//                 "main_tag": "string",
//                 "title": "string",
//                 "description": "string",
//             }
//         ]
//     }
// }

export const UniversalSchema = {

  // ─────────────────────────────────────────────
  // 0. ANALYSIS IDENTITY
  //    Drives: page <title>, header eyebrow/badge, footer brand line, nav logo
  // ─────────────────────────────────────────────
  analysis_identity: {
    /** Internal slug used for routing / filenames */
    id: "string",                        // e.g. "sivanna-vs-eveline-2025"

    /** Names of the two entities being compared — order matters (index 0 = "your brand") */
    competitors: ["string", "string"],   // e.g. ["Sivanna Colors", "Eveline Pakistan"]

    /** Short human-readable description shown in the header subtitle */
    description: "string",

    /** Market / industry context used in header eyebrow badge */
    market_context: "string",            // e.g. "Pakistan Beauty Market · 2025"

    /** Keyword chips shown below the header title */
    tags: [
      {
        label: "string",                 // e.g. "Sivanna Colors · Eyes · Foundation"
        variant: "string",               // one of: "primary" | "secondary" | "neutral"
      }
    ],

    /** @optional — competitor brand colors used for theming the entire report */
    brand_colors: [
      {
        competitor: "string",            // matches competitors[] entry
        primary: "string",               // hex, e.g. "#B5525C"
        light: "string",                 // hex with opacity for fills
        soft: "string",                  // hex with low opacity for backgrounds
      }
    ],

    /** @optional — website URLs for each competitor */
    urls: [
      {
        competitor: "string",
        url: "string",
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 1. EXECUTIVE SUMMARY  (Section 01 — "At a Glance")
  //    Drives: metric strip + scorecard side-by-side
  // ─────────────────────────────────────────────
  executive_summary: {
    title: "string",                     // e.g. "At a Glance"
    subtitle: "string",                  // e.g. "Key quantitative signals and brand snapshot from both sites"

    /**
     * KPI strip — 3 to 6 headline numbers displayed in a horizontal grid.
     * Each cell can show one value (neutral) OR two values (one per competitor).
     */
    kpi_strip: [
      {
        label: "string",                 // e.g. "Total SKUs", "Entry Price / yr"
        values: [
          {
            competitor: "string",        // matches competitors[] entry, or null for neutral
            value: "string",             // e.g. "42", "₨695", "4.9 / 5", "—"
            is_null: false,              // true → render as em-dash / greyed out
          }
        ],
      }
    ],

    /**
     * Scorecard — one card per competitor shown side-by-side with a "VS" badge.
     */
    scorecards: [
      {
        competitor: "string",            // matches competitors[] entry
        role_label: "string",            // e.g. "Your Brand", "Competitor", "Marketplace"
        origin: "string",                // @optional — e.g. "🇹🇭 Thailand · sivanna.com.pk"
        stats: [
          {
            value: "string",             // e.g. "18", "₨750", "4.9★", "Since 1991"
            label: "string",             // e.g. "Eyes Collection SKUs", "Entry Price"
          }
        ],
      }
    ],

    /**
     * @optional — radar chart comparing both competitors across N dimensions.
     * Shown in the overview when a high-level visual score is needed.
     */
    radar_chart: {
      title: "string",
      subtitle: "string",
      dimensions: ["string"],            // axis labels, e.g. ["Catalog Depth", "Price Access.", ...]
      datasets: [
        {
          competitor: "string",
          scores: [0],                   // numeric, same length as dimensions[]
        }
      ],
    },

    /**
     * @optional — bubble chart (inventory breadth vs conversion tooling, etc.)
     */
    bubble_chart: {
      title: "string",
      subtitle: "string",
      x_axis_label: "string",
      y_axis_label: "string",
      datasets: [
        {
          competitor: "string",
          x: 0,
          y: 0,
          r: 0,                          // bubble radius (proportional to a third metric)
        }
      ],
    },
  },

  // ─────────────────────────────────────────────
  // 2. POSITIONING & MESSAGING  (Section 02)
  //    Drives: positioning cards + messaging bar chart + overlap cards
  // ─────────────────────────────────────────────
  positioning: {
    title: "string",
    subtitle: "string",

    /** One card per competitor — a structured list of key positioning attributes */
    cards: [
      {
        competitor: "string",
        rows: [
          {
            label: "string",             // e.g. "Headline", "Promise", "Primary CTA"
            value: "string",
          }
        ],
      }
    ],

    /**
     * @optional — bar chart scoring how strongly each signal appears in the messaging
     */
    messaging_chart: {
      title: "string",
      subtitle: "string",
      dimensions: ["string"],            // e.g. ["Market coverage", "Discounts/price", ...]
      datasets: [
        {
          competitor: "string",
          scores: [0],                   // 1–10, same length as dimensions[]
        }
      ],
    },

    /**
     * @optional — overlap and differentiation summary cards
     */
    overlap_cards: [
      {
        label: "string",                 // e.g. "Shared overlaps", "Value proposition"
        items: ["string"],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 3. FEATURE MATRIX  (Section 03)
  //    Drives: feature table + bar/donut summary charts
  // ─────────────────────────────────────────────
  feature_matrix: {
    title: "string",
    subtitle: "string",

    /**
     * Comparison table — each row is a feature/capability dimension.
     * "winner" drives the win-chip badge color.
     */
    table: {
      headers: ["string"],               // e.g. ["Category / Dimension", "Brand A", "Brand B", "Edge"]
      rows: [
        {
          dimension: "string",           // e.g. "Drag & Drop Builder", "Advisory / Sales assist"
          values: [
            {
              competitor: "string",
              description: "string",     // prose cell content
              status: "string",          // one of: "yes" | "no" | "partial" | "exclusive" | "na"
            }
          ],
          winner: "string",              // competitor name OR "tie" OR null
          winner_note: "string",         // @optional — e.g. "(AOV potential)"
        }
      ],
    },

    /**
     * @optional — summary charts derived from the table above
     */
    summary_charts: [
      {
        type: "string",                  // one of: "bar" | "doughnut" | "radar"
        title: "string",
        subtitle: "string",
        /** For doughnut — breakdown of who leads */
        breakdown: [
          {
            label: "string",             // e.g. "Brand A leads", "Brand B leads", "Roughly equal"
            value: 0,
          }
        ],
        /** For bar — per-competitor scores on dimensions */
        datasets: [
          {
            competitor: "string",
            scores: [0],
          }
        ],
        dimensions: ["string"],          // axis labels (used for bar type)
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 4. PRICING ANALYSIS  (Section 02 or 04 depending on report type)
  //    Drives: price range bars, price tier charts, pricing plan tables
  // ─────────────────────────────────────────────
  price_analysis: {
    title: "string",
    subtitle: "string",

    /**
     * Per-collection or per-product-line price ranges.
     * Used to render the horizontal price-span visual.
     */
    price_ranges: [
      {
        competitor: "string",
        segment: "string",               // e.g. "Eyes", "Foundation", "Makeup", "BB Creams"
        min: 0,                          // numeric (no currency symbol)
        max: 0,
        avg: 0,                          // @optional — midpoint or weighted average
        currency: "string",              // e.g. "PKR", "USD", "GBP"
        currency_symbol: "string",       // e.g. "₨", "$", "£"
        scale_max: 0,                    // @optional — axis max for the visual track
      }
    ],

    /**
     * @optional — structured pricing plan tables (SaaS / subscription model reports)
     */
    pricing_plans: [
      {
        competitor: "string",
        plan_type: "string",             // e.g. "Annual", "Lifetime", "Monthly"
        is_unique_advantage: false,      // true → render "UNIQUE ADVANTAGE" badge
        plans: [
          {
            name: "string",              // e.g. "Single Site License", "Elite"
            price: 0,                    // numeric
            original_price: 0,           // @optional — pre-discount price
            currency: "string",
            billing_period: "string",    // e.g. "yr", "mo", "one-time"
            sites: "string",             // e.g. "1 Domain", "3 Sites", "Unlimited"
            description: "string",       // feature summary for this plan
            badge: "string",             // @optional — e.g. "20% OFF", "Most Popular"
          }
        ],
      }
    ],

    /**
     * @optional — charts for pricing section
     */
    charts: [
      {
        type: "string",                  // one of: "bar" | "bubble"
        title: "string",
        subtitle: "string",
        datasets: [
          {
            competitor: "string",
            data: [
              {
                label: "string",         // x-axis label
                min: 0,                  // @optional
                max: 0,                  // @optional
                avg: 0,                  // @optional
                value: 0,                // for single-value bars
                x: 0,                    // for bubble
                y: 0,                    // for bubble
                r: 0,                    // for bubble
              }
            ],
          }
        ],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 5. COLLECTION / CATALOG DATA TABLE  (Section 03 — store reports)
  //    Drives: the detailed collection-level tabular view
  //    @optional — only present in e-commerce / store comparison reports
  // ─────────────────────────────────────────────
  collection_data: {
    title: "string",
    subtitle: "string",
    footnote: "string",                  // @optional — e.g. "* OOS count may include variant level"
    table: {
      headers: ["string"],               // e.g. ["Store", "Collection", "Products", "Price Min", ...]
      rows: [
        {
          competitor: "string",
          collection: "string",          // e.g. "Eyes", "Foundation"
          product_count: 0,
          price_min: 0,
          price_max: 0,
          currency_symbol: "string",
          has_filters: true,
          in_stock: "string",            // numeric string or "—" (null)
          out_of_stock: "string",        // numeric string or "—" (null)
          note: "string",                // @optional — e.g. "Out of Stock · 50%"
        }
      ],
    },
    // i have to show list of products for each competitor
    product_lists: [
        {
            competitor: "string",
            collection: "string",
            products: [
                {
                    name: "string",
                    price: 0,
                    currency_symbol: "string",
                    in_stock: true,
                    filters: ["string"], // e.g. ["Matte", "Long-lasting", "Waterproof"]
                    image_url: "string", // URL to product image for visual cards
                    url: "string",       // @optional — link to product page
                }
            ]
        }
    ]
  },

  // ─────────────────────────────────────────────
  // 6. QUANTITATIVE SIGNALS  (Section 04 — service/marketplace reports)
  //    Drives: inventory count charts + claims table
  //    @optional — present in service/marketplace comparison reports
  // ─────────────────────────────────────────────
  quantitative_signals: {
    title: "string",
    subtitle: "string",
    table: {
      headers: ["string"],               // e.g. ["Metric", "Brand A", "Brand B"]
      rows: [
        {
          metric: "string",              // e.g. "Response time", "Google rating"
          values: [
            {
              competitor: "string",
              value: "string",           // e.g. "15-minute average response", "— Not stated"
              is_null: false,
            }
          ],
        }
      ],
    },
    charts: [
      {
        type: "string",                  // one of: "bar" | "bubble"
        title: "string",
        subtitle: "string",
        datasets: [
          {
            competitor: "string",
            data: [{ label: "string", value: 0 }],
          }
        ],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 7. TRUST SIGNALS & CONVERSION ASSETS  (Section 05 — SaaS/service reports)
  //    Drives: social proof cards + conversion asset cards + trust score chart
  //    @optional — present in SaaS or service comparison reports
  // ─────────────────────────────────────────────
  trust_signals: {
    title: "string",
    subtitle: "string",

    social_proof: [
      {
        competitor: "string",
        items: [
          {
            label: "string",             // e.g. "User Volume", "Brand Logos", "External Review"
            value: "string",
          }
        ],
      }
    ],

    conversion_assets: [
      {
        competitor: "string",
        items: [
          {
            label: "string",             // e.g. "Free Option", "Demo", "Risk Reversal"
            value: "string",
          }
        ],
      }
    ],

    /** @optional — bar chart scoring trust signal strength across dimensions */
    trust_chart: {
      title: "string",
      subtitle: "string",
      dimensions: ["string"],
      datasets: [
        {
          competitor: "string",
          scores: [0],
        }
      ],
    },
  },

  // ─────────────────────────────────────────────
  // 8. SEO & METADATA  (Section 06 in Fluent/Gravity; Section 06 in Sivanna/Eveline)
  //    Drives: SEO quality cards + SEO score bar chart
  // ─────────────────────────────────────────────
  seo_analysis: {
    title: "string",
    subtitle: "string",

    cards: [
      {
        competitor: "string",
        quality_label: "string",         // e.g. "✓ Descriptive & Keyword-Rich", "⚠ Generic / Low Detail"
        quality_level: "string",         // one of: "high" | "medium" | "low"

        /** Structured metadata fields */
        fields: [
          {
            label: "string",             // e.g. "Page Title", "Meta Description", "OG Last Modified"
            value: "string",
            is_positive: false,          // @optional — drives green/amber color
          }
        ],

        /** @optional — collection-level examples (e-commerce reports) */
        examples: [
          {
            collection: "string",
            title: "string",
            meta_description: "string",
          }
        ],

        summary: "string",               // @optional — prose summary paragraph
      }
    ],

    /** @optional — bar chart for SEO dimension scores */
    seo_chart: {
      title: "string",
      subtitle: "string",
      dimensions: ["string"],            // e.g. ["Title Keyword Richness", "Meta Description Quality", ...]
      datasets: [
        {
          competitor: "string",
          scores: [0],                   // 0–10
        }
      ],
    },

    /**
     * @optional — analytics / tracking stack comparison (Fluent × Gravity style)
     */
    tracking_stack: [
      {
        category: "string",              // e.g. "Analytics", "Advertising", "Tag Management"
        values: [
          {
            competitor: "string",
            value: "string",
          }
        ],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 9. SWOT ANALYSIS  (Section 07 in store report; Section 05 in others)
  //    Drives: 2×2 SWOT grid per competitor
  // ─────────────────────────────────────────────
  swot_analysis: {
    title: "string",
    subtitle: "string",

    competitors: [
      {
        competitor: "string",
        description: "string",           // @optional — tagline or context blurb
        quadrants: {
          strengths: ["string"],
          weaknesses: ["string"],
          opportunities: ["string"],
          threats: ["string"],
        },
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 10. KEY INSIGHTS  (Section 06 in Hubble/KOG; Section 08 in Fluent/Gravity)
  //     Drives: insight cards grid
  // ─────────────────────────────────────────────
  key_insights: {
    title: "string",
    subtitle: "string",

    insights: [
      {
        /** Short theme tag shown above the card title, e.g. "Conversion strategy" */
        theme: "string",

        /** @optional — sequential number displayed in monospace above the title */
        number: "string",                // e.g. "01", "02"

        title: "string",
        description: "string",
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 11. RECOMMENDATIONS  (Section 08 in store report; Section 07 in others)
  //     Drives: two-column recommendation panels per competitor
  // ─────────────────────────────────────────────
  recommendations: {
    title: "string",
    subtitle: "string",

    competitor_specific: [
      {
        competitor: "string",
        panel_heading: "string",         // e.g. "Sivanna Colors — Priority Actions"

        recommendations: [
          {
            /** Sequential index shown in monospace, e.g. "01" */
            index: "string",

            /**
             * Priority level — drives dot color in Hubble/KOG style panels.
             * @optional — omit for simpler numbered-list style (store report)
             */
            priority: "string",          // one of: "high" | "medium" | "low"

            /** Recommendation body — may include <strong> emphasis for the action verb */
            action: "string",

            /** Expected business impact — shown below the action in smaller muted text */
            impact: "string",
          }
        ],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 12. TOP PRODUCTS  (Section 05 — store comparison reports only)
  //     Drives: product lists by price per competitor
  //     @optional — only present in e-commerce reports
  // ─────────────────────────────────────────────
  top_products: {
    title: "string",
    subtitle: "string",

    lists: [
      {
        competitor: "string",
        list_heading: "string",          // e.g. "Sivanna — Highest Priced"
        products: [
          {
            name: "string",
            collection: "string",        // e.g. "Foundation Collection"
            price: 0,
            currency_symbol: "string",
            note: "string",              // @optional — e.g. "Out of Stock", "50% at Checkout"
          }
        ],
      }
    ],
  },

  // ─────────────────────────────────────────────
  // 13. PORTFOLIO & COMPETITIVE MATRIX  (Section 04 — store reports)
  //     Drives: full comparison table + stock donut + radar
  //     @optional — e-commerce variant of feature_matrix
  // ─────────────────────────────────────────────
  portfolio_matrix: {
    title: "string",
    subtitle: "string",

    /** Full comparison table — mirrors feature_matrix.table but with free-form cells */
    table: {
      headers: ["string"],               // e.g. ["Dimension", "Brand A", "Brand B", "Edge"]
      rows: [
        {
          dimension: "string",
          values: [
            {
              competitor: "string",
              description: "string",
              is_warning: false,         // @optional — red color for critical issues
            }
          ],
          winner: "string",              // competitor name | "tie"
          winner_note: "string",         // @optional
        }
      ],
    },

    /**
     * @optional — supporting charts (radar, donut, bar)
     */
    charts: [
      {
        type: "string",                  // one of: "radar" | "doughnut" | "bar"
        title: "string",
        subtitle: "string",
        dimensions: ["string"],
        datasets: [
          {
            competitor: "string",
            scores: [0],
          }
        ],
        /** For doughnut — legend labels with values */
        breakdown: [
          {
            label: "string",
            value: 0,
          }
        ],
      }
    ],
  },

};