import { v4 as uuidv4 } from "uuid";

// First path segments that ALREADY encode the top-level bucket (Shopify-style
// stores, WooCommerce with a shop/product base, blog/page prefixes). For these
// the URL path gives us the hierarchy, so we leave the tree exactly as-is. Any
// OTHER first segment (root-level permalinks like /bolero/, /product-slug/) has
// no structure to nest under, so we fall back to the catalog bucket instead.
const STRUCTURAL_FIRST_SEGMENTS = new Set([
    "collections", "collection", "products", "product",
    "product-category", "product-cat", "product-tag", "product_cat",
    "shop", "store", "category", "categories", "catalog",
    "c", "w", "p", "pages", "page", "blogs", "blog", "news", "policies",
]);

const slugifyGroup = (label) =>
    "grp-" + String(label).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");

class UrlTree {
    constructor(options = {}) {
        this.root = {};

        this.pagesToExclude = new Set(
            options.pagesToExclude || []
        );

        this.pagesCategory = {
            id: uuidv4(),
            name: "pages",
            slug: "pages",
            path: "/pages",
            url: null,
            selected: false,
            children: {},
        };
    }

    shouldExclude(pathname) {
        for (const page of this.pagesToExclude) {
            if (page === "home") continue;

            if (
                pathname === page ||
                pathname.startsWith(page + "/")
            ) {
                return true;
            }
        }

        return false;
    }

    insertMany(items) {
        for (const item of items) {
            this.insert(item);
        }
    }

    createNode(name, slug, path, url = null) {
        return {
            id: uuidv4(),
            name,
            slug,
            path,
            url,
            selected: false,
            children: {},
        };
    }

    insert(input, bucketLabel = null) {
        if (Array.isArray(input)) {
            this.insertMany(input);
            return;
        }

        if (input instanceof Set) {
            this.insertMany([...input]);
            return;
        }

        // Entries can be a plain URL string or a { url, title, groups } object.
        // `title` becomes the leaf name (real product/collection name); `groups`
        // is an ordered list of auto-bucket labels (outermost first) that inject
        // that many header levels — e.g. ["Men","Bottom"] → collections/products
        // › Men › Bottom › item. Legacy single `group` string is also accepted.
        let title = null;
        let groups = [];
        let count = null;
        let inNav = false;
        let kind = null;
        let url = input;

        if (input && typeof input === "object") {
            if (input.categories && typeof input.categories === "object") {
                // Carry the bucket name (Collections / Products / …) so entries whose
                // URL has no structural prefix still nest under the right top-level
                // tab instead of collapsing into a flat list.
                for (const [bucket, value] of Object.entries(input.categories)) {
                    if (!Array.isArray(value)) continue;
                    for (const entry of value) this.insert(entry, bucket);
                }
                return;
            }

            if (typeof input.url === "string") {
                url = input.url;
                title = typeof input.title === "string" && input.title.trim()
                    ? input.title.trim()
                    : null;
                if (Array.isArray(input.groups)) {
                    groups = input.groups
                        .filter((g) => typeof g === "string" && g.trim())
                        .map((g) => g.trim());
                } else if (typeof input.group === "string" && input.group.trim()) {
                    groups = [input.group.trim()];
                }
                if (typeof input.count === "number" && input.count >= 0) {
                    count = input.count;
                }
                if (input.inNav === true) inNav = true;
                if (typeof input.kind === "string") kind = input.kind;
            } else {
                return;
            }
        }

        try {
            const parsed = new URL(url);

            const origin = parsed.origin;

            const parts = parsed.pathname
                .split("/")
                .filter(Boolean);

            // Homepage
            if (parts.length === 0) {
                if (this.pagesToExclude.has("home")) {
                    return;
                }

                this.root.home ??= this.createNode(
                    "Home",
                    "home",
                    "/",
                    url
                );

                return;
            }

            // Excluded pages
            if (this.shouldExclude(parsed.pathname)) {
                return;
            }

            // Root file
            if (
                parts.length === 1 &&
                parts[0].includes(".")
            ) {
                const file = parts[0];

                this.pagesCategory.children[file] ??=
                    this.createNode(
                        file,
                        file,
                        `/${file}`,
                        url
                    );

                return;
            }

            // Inject synthetic header levels (url null → not selectable) so the
            // tree nests nicely. Two sources feed this:
            //   • `groups` — auto-buckets like ["Men","Bottom"] from the catalog.
            //   • the catalog `bucket` (Collections/Products/…) — used ONLY when the
            //     URL's first segment isn't structural (root-level permalinks), so
            //     e.g. /bolero/ lands under "Collections" instead of the flat list.
            const groupLabelByIndex = {};
            const groupSlugSet = new Set();
            let effectiveParts = parts;

            const firstSeg = (parts[0] || "").toLowerCase();
            const needsBucket =
                !!bucketLabel && !STRUCTURAL_FIRST_SEGMENTS.has(firstSeg);

            if (needsBucket) {
                // Bucket › [groups] › <full real path>. The bucket header is the
                // top-level tab; the whole permalink sits beneath it.
                const bucketSlug = slugifyGroup("bucket-" + bucketLabel);
                const groupSlugs = groups.map(slugifyGroup);
                groupSlugSet.add(bucketSlug);
                groupSlugs.forEach((s) => groupSlugSet.add(s));
                effectiveParts = [bucketSlug, ...groupSlugs, ...parts];
                groupLabelByIndex[0] = bucketLabel;
                groups.forEach((label, i) => { groupLabelByIndex[1 + i] = label; });
            } else if (groups.length && parts.length >= 2) {
                const slugs = groups.map(slugifyGroup);
                slugs.forEach((s) => groupSlugSet.add(s));
                effectiveParts = [parts[0], ...slugs, ...parts.slice(1)];
                groups.forEach((label, i) => { groupLabelByIndex[1 + i] = label; });
            }

            let current = this.root;

            effectiveParts.forEach((part, index) => {
                const isLeaf = index === effectiveParts.length - 1;
                const groupLabel = groupLabelByIndex[index];
                const isGroup = groupLabel !== undefined;

                const sliceParts = effectiveParts.slice(0, index + 1);
                const syntheticPath = "/" + sliceParts.join("/");
                // The REAL path excludes synthetic grp-* segments — those exist
                // ONLY for tree nesting and must never leak into a url/path.
                const realPath = "/" + sliceParts.filter((p) => !groupSlugSet.has(p)).join("/");

                // Group headers aren't real pages → no url (not selectable). Leaf →
                // its original url (keeps query/hash). Intermediate → real base path.
                const currentUrl = isGroup ? null : isLeaf ? url : origin + realPath;

                // `path` is metadata some consumers (e.g. sidebar links) treat as
                // the real URL path. Real nodes expose their actual path; only the
                // group headers keep the synthetic path (they carry no url anyway).
                const nodePath = isGroup ? syntheticPath : realPath;

                // Group node → the bucket label; leaf → the real title; else the
                // prettified slug for intermediate path segments.
                const nodeName = isGroup
                    ? groupLabel
                    : isLeaf && title
                        ? title
                        : decodeURIComponent(part).replace(/-/g, " ").trim();

                if (!current[part]) {
                    current[part] = this.createNode(nodeName, part, nodePath, currentUrl);
                } else if (isLeaf && title) {
                    // Node created earlier from a URL-only source — upgrade its label.
                    current[part].name = title;
                }

                // Product count belongs on the selectable leaf (the collection itself).
                if (isLeaf && count !== null) {
                    current[part].count = count;
                }

                // Nav membership + collection kind (category/brand/marketing) ride on
                // the selectable leaf, so the picker can badge and prioritise it.
                if (isLeaf && inNav) current[part].inNav = true;
                if (isLeaf && kind) current[part].kind = kind;

                current = current[part].children;
            });
        } catch (err) {
            console.warn("Invalid URL:", url);
        }
    }

    finalize() {
        // Merge /pages/*
        if (this.root.pages) {
            this.pagesCategory.children = {
                ...this.root.pages.children,
                ...this.pagesCategory.children,
            };

            delete this.root.pages;
        }

        // Move standalone root pages
        const remove = [];

        for (const [key, value] of Object.entries(this.root)) {
            const hasChildren =
                Object.keys(value.children).length > 0;

            if (!hasChildren) {
                this.pagesCategory.children[key] = value;
                remove.push(key);
            }
        }

        remove.forEach((key) => delete this.root[key]);

        if (
            Object.keys(this.pagesCategory.children).length
        ) {
            this.root.pages = this.pagesCategory;
        }

        return this.root;
    }

    toJSON() {
        return this.finalize();
    }

    get size() {
        let total = 0;

        function walk(nodes) {
            for (const node of Object.values(nodes)) {
                total++;
                walk(node.children);
            }
        }

        walk(this.root);

        return total;
    }
}

export default UrlTree;