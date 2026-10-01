// Step 4 — Industry → Category → Subcategory.
//
// A FIXED taxonomy so every store (owner and competitors) is described in the
// same vocabulary — "Beauty → Makeup → Lip" can be compared, a free-text AI
// phrase like "color cosmetics" can't. The AI only PICKS a path from this list
// (validated); a deterministic keyword scorer is the fallback and the tiebreak.
//
// Keywords are matched as whole words against category names, product types and
// product titles (plural "s"/"es" tolerated). Keep them specific: generic words
// ("set", "pack", "new") would pull every store into the wrong branch.

export const TAXONOMY = {
    Fashion: {
        "Women's Clothing": {
            Dresses: ["dress", "gown", "maxi", "frock"],
            "Eastern Wear": ["lawn", "kurti", "kurta", "shalwar", "kameez", "abaya", "dupatta", "unstitched", "stitched", "saree", "sari", "lehenga", "pret", "jalabiya"],
            "Tops & Shirts": ["blouse", "top", "tee", "t-shirt", "tshirt", "shirt", "tunic", "cami"],
            "Bottoms": ["jeans", "trouser", "pant", "skirt", "short", "culotte", "palazzo"],
            Outerwear: ["jacket", "coat", "blazer", "cardigan", "hoodie", "sweater", "shawl"],
            "Lingerie & Sleepwear": ["bra", "lingerie", "panty", "nightwear", "sleepwear", "pajama", "pyjama", "loungewear"],
        },
        "Men's Clothing": {
            Shirts: ["shirt", "polo", "tee", "t-shirt", "tshirt", "henley"],
            "Eastern Wear": ["kurta", "shalwar", "kameez", "waistcoat", "sherwani", "thobe", "kandura"],
            Bottoms: ["jeans", "chino", "trouser", "pant", "short", "jogger"],
            "Suits & Formal": ["suit", "blazer", "tuxedo", "formal"],
            Outerwear: ["jacket", "coat", "hoodie", "sweater", "sweatshirt", "puffer"],
        },
        "Kids' Clothing": {
            Baby: ["baby", "infant", "newborn", "romper", "onesie", "toddler"],
            Girls: ["girls"],
            Boys: ["boys"],
        },
        Activewear: {
            "Gym & Training": ["activewear", "gym", "workout", "training", "sports bra", "leggings", "legging", "tank", "athleisure"],
            "Running": ["running", "runner"],
            "Yoga": ["yoga", "pilates"],
        },
        Footwear: {
            "Athletic Shoes": ["sneaker", "trainer", "running shoe", "sports shoe"],
            "Casual Shoes": ["loafer", "moccasin", "slip-on", "espadrille", "chappal", "slipper", "sandal", "slide", "flip flop", "khussa"],
            "Formal Shoes": ["oxford", "derby", "brogue", "formal shoe", "heel", "pump", "stiletto"],
            Boots: ["boot", "chelsea"],
        },
        Accessories: {
            Bags: ["bag", "handbag", "backpack", "tote", "clutch", "wallet", "purse", "luggage"],
            Jewellery: ["jewelry", "jewellery", "earring", "necklace", "bracelet", "ring", "pendant", "bangle", "anklet"],
            Watches: ["watch", "smartwatch"],
            Eyewear: ["sunglasses", "eyewear", "glasses", "spectacle"],
            "Hats, Belts & Scarves": ["cap", "hat", "beanie", "belt", "scarf", "stole", "tie", "cufflink"],
        },
    },
    Beauty: {
        Makeup: {
            Face: ["foundation", "concealer", "primer", "powder", "blush", "bronzer", "highlighter", "contour", "bb cream", "cc cream"],
            Eyes: ["mascara", "eyeliner", "eyeshadow", "kajal", "kohl", "brow", "lash"],
            Lips: ["lipstick", "lip gloss", "lip liner", "lip balm", "lip tint", "lip"],
            Nails: ["nail polish", "nail", "manicure"],
            "Tools & Brushes": ["brush", "sponge", "blender", "makeup tool"],
        },
        Skincare: {
            "Cleansers & Toners": ["cleanser", "face wash", "toner", "micellar"],
            "Serums & Treatments": ["serum", "retinol", "niacinamide", "vitamin c", "acid", "ampoule", "essence"],
            Moisturisers: ["moisturizer", "moisturiser", "cream", "lotion", "gel cream"],
            "Sun Care": ["sunscreen", "spf", "sunblock"],
            Masks: ["mask", "sheet mask", "peel"],
        },
        "Hair Care": {
            "Shampoo & Conditioner": ["shampoo", "conditioner"],
            "Styling & Treatments": ["hair oil", "hair serum", "hair mask", "hair spray", "styling", "hair color", "hair dye"],
            "Hair Tools": ["straightener", "curler", "hair dryer", "blow dryer"],
        },
        Fragrance: {
            Perfume: ["perfume", "fragrance", "eau de parfum", "edp", "edt", "cologne", "attar", "oud", "body mist"],
        },
        "Bath & Body": {
            "Body Care": ["body wash", "shower gel", "body lotion", "body butter", "scrub", "soap", "deodorant"],
        },
    },
    Electronics: {
        "Mobile & Tablets": {
            Smartphones: ["smartphone", "iphone", "android", "mobile phone", "galaxy"],
            Tablets: ["tablet", "ipad"],
            "Mobile Accessories": ["charger", "power bank", "phone case", "cable", "screen protector", "earbud", "airpods"],
        },
        Computing: {
            Laptops: ["laptop", "notebook", "macbook", "ultrabook", "chromebook"],
            "Gaming PCs": ["gaming pc", "gaming desktop", "rtx", "gpu", "graphics card"],
            "PC Components": ["ssd", "ram", "motherboard", "processor", "cpu", "psu"],
            Peripherals: ["keyboard", "mouse", "monitor", "webcam", "printer", "router"],
        },
        "Audio & Video": {
            Audio: ["headphone", "earphone", "speaker", "soundbar", "earbuds"],
            "TV & Video": ["tv", "television", "led tv", "projector"],
            Cameras: ["camera", "lens", "dslr", "gopro"],
        },
        "Gaming": {
            "Consoles & Games": ["playstation", "ps5", "xbox", "nintendo", "console", "controller", "video game"],
        },
        "Wearables & Smart Home": {
            Wearables: ["smartwatch", "fitness tracker", "smart band"],
            "Smart Home": ["smart plug", "smart bulb", "security camera", "doorbell"],
        },
    },
    "Home & Living": {
        Furniture: {
            "Living Room": ["sofa", "couch", "coffee table", "tv unit", "recliner"],
            Bedroom: ["bed", "wardrobe", "mattress", "dresser", "nightstand"],
            "Office Furniture": ["office chair", "desk", "study table"],
        },
        "Home Decor": {
            Decor: ["decor", "vase", "wall art", "frame", "candle", "mirror", "clock", "artificial plant"],
            Lighting: ["lamp", "lighting", "chandelier", "pendant light"],
            "Rugs & Curtains": ["rug", "carpet", "curtain", "blind"],
        },
        "Bedding & Bath": {
            Bedding: ["bedsheet", "bed sheet", "duvet", "comforter", "pillow", "quilt", "blanket"],
            Bath: ["towel", "bathrobe", "bath mat"],
        },
        "Kitchen & Dining": {
            Cookware: ["cookware", "pan", "pot", "wok", "pressure cooker"],
            Dinnerware: ["dinner set", "plate", "mug", "cup", "glassware", "cutlery", "crockery"],
            Storage: ["container", "storage", "jar", "organizer"],
        },
    },
    Appliances: {
        "Kitchen Appliances": {
            "Small Kitchen Appliances": ["air fryer", "blender", "juicer", "microwave", "oven", "toaster", "kettle", "coffee machine", "food processor", "chopper"],
        },
        "Large Appliances": {
            "Large Appliances": ["refrigerator", "fridge", "washing machine", "dryer", "dishwasher", "air conditioner", "deep freezer", "water dispenser"],
        },
        "Personal Care Appliances": {
            Grooming: ["trimmer", "shaver", "epilator", "hair clipper"],
        },
    },
    "Health & Wellness": {
        Supplements: {
            "Vitamins & Supplements": ["vitamin", "supplement", "protein", "whey", "creatine", "collagen", "omega", "multivitamin", "gummies"],
        },
        "Personal Health": {
            "Medical Devices": ["thermometer", "blood pressure", "glucometer", "nebulizer", "oximeter"],
            "Sexual Wellness": ["condom", "lubricant"],
        },
    },
    "Sports & Outdoors": {
        "Fitness Equipment": {
            "Gym Equipment": ["dumbbell", "kettlebell", "treadmill", "exercise bike", "yoga mat", "resistance band", "barbell"],
        },
        "Outdoor & Camping": {
            Camping: ["tent", "sleeping bag", "camping", "hiking", "trekking"],
        },
        "Team & Racket Sports": {
            "Sports Gear": ["cricket", "football", "bat", "racket", "tennis", "badminton", "hockey", "golf"],
        },
        Cycling: {
            Bikes: ["bicycle", "cycle", "bike", "helmet"],
        },
    },
    "Baby & Kids": {
        "Baby Care": {
            "Diapers & Care": ["diaper", "nappy", "wipes", "baby lotion", "feeding bottle", "pacifier"],
            "Baby Gear": ["stroller", "pram", "car seat", "baby carrier", "crib", "cot"],
        },
        Toys: {
            Toys: ["toy", "lego", "puzzle", "doll", "action figure", "board game", "plush", "rc car"],
        },
    },
    "Food & Grocery": {
        Grocery: {
            Pantry: ["rice", "flour", "spice", "masala", "oil", "ghee", "pulses", "lentil", "sauce", "pasta"],
            Snacks: ["snack", "chips", "biscuit", "cookie", "chocolate", "candy", "nuts", "dry fruit"],
            Beverages: ["tea", "coffee", "juice", "drink", "beverage"],
        },
        "Specialty Food": {
            "Gourmet & Organic": ["organic", "honey", "gourmet", "bakery", "cake"],
        },
    },
    "Pets": {
        "Pet Supplies": {
            "Pet Food & Care": ["dog", "cat", "pet food", "litter", "leash", "collar", "aquarium"],
        },
    },
    "Books & Stationery": {
        Books: {
            Books: ["book", "novel", "paperback", "hardcover", "ebook"],
        },
        Stationery: {
            "Office & School": ["notebook", "pen", "pencil", "planner", "diary", "stationery", "art supplies"],
        },
    },
    Automotive: {
        "Car & Bike Accessories": {
            Accessories: ["car accessories", "car seat cover", "dash cam", "tyre", "tire", "motor oil", "car care", "helmet visor"],
        },
    },
    "Gifts & Occasions": {
        Gifts: {
            "Gifts & Hampers": ["gift box", "hamper", "gift set", "flowers", "bouquet", "greeting card"],
        },
    },
};

const INDUSTRIES = Object.keys(TAXONOMY);

/** Every valid "Industry > Category > Subcategory" path. */
export const allPaths = () => {
    const out = [];
    for (const [ind, cats] of Object.entries(TAXONOMY)) {
        for (const [cat, subs] of Object.entries(cats)) {
            for (const sub of Object.keys(subs)) out.push([ind, cat, sub]);
        }
    }
    return out;
};

const norm = (s) => ` ${String(s || "").toLowerCase().replace(/[^a-z0-9&+'\- ]+/g, " ").replace(/\s+/g, " ").trim()} `;
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const kwRe = new Map();
const keywordRegex = (kw) => {
    if (!kwRe.has(kw)) kwRe.set(kw, new RegExp(` ${escapeRe(kw.toLowerCase())}(?:s|es)? `));
    return kwRe.get(kw);
};

/**
 * Deterministic scorer. `texts` are category names / product types / titles.
 * Category & type labels weigh more than titles (they describe the catalog).
 * Returns { ranked:[{path, score}], industryScores:{industry:score} }.
 */
export const keywordClassify = ({ categories = [], productTypes = [], titles = [] } = {}) => {
    const weighted = [
        ...categories.map((t) => [norm(t), 3]),
        ...productTypes.map((t) => [norm(t), 3]),
        ...titles.map((t) => [norm(t), 1]),
    ];
    const scores = new Map();
    const industryScores = {};
    for (const [ind, cats] of Object.entries(TAXONOMY)) {
        for (const [cat, subs] of Object.entries(cats)) {
            for (const [sub, kws] of Object.entries(subs)) {
                let score = 0;
                for (const [text, w] of weighted) {
                    // One hit per text — a title listing "shirt, shirt, shirt"
                    // shouldn't outweigh the catalog's breadth.
                    if (kws.some((kw) => keywordRegex(kw).test(text))) score += w;
                }
                if (score > 0) {
                    scores.set(`${ind}|${cat}|${sub}`, score);
                    industryScores[ind] = (industryScores[ind] || 0) + score;
                }
            }
        }
    }
    const ranked = [...scores.entries()]
        .map(([k, score]) => ({ path: k.split("|"), score }))
        .sort((a, b) => b.score - a.score);
    return { ranked, industryScores };
};

// An industry counts toward breadth only if it carries a real share of the
// catalog — one stray "candle" in a fashion store isn't a Home & Living line.
const significantIndustries = (industryScores, minShare = 0.12) => {
    const total = Object.values(industryScores).reduce((a, b) => a + b, 0) || 1;
    return Object.entries(industryScores)
        .filter(([, s]) => s / total >= minShare)
        .sort((a, b) => b[1] - a[1])
        .map(([ind]) => ind);
};

export const isValidPath = (ind, cat, sub) => Boolean(TAXONOMY[ind]?.[cat]?.[sub]);

const pathString = (p) => p.filter(Boolean).join(" → ");

/** Build store_taxonomy_v1 from a keyword result (no AI). */
export const taxonomyFromKeywords = (input) => {
    const { ranked, industryScores } = keywordClassify(input);
    const industries = significantIndustries(industryScores);
    const top = ranked.find((r) => r.path[0] === industries[0]) || ranked[0];
    if (!top) {
        return { schemaVersion: "store_taxonomy_v1", industry: null, category: null, subcategory: null, path: null,
                 industries: [], industryCount: 0, brandModel: null, confidence: "low", source: "none" };
    }
    const [industry, category, subcategory] = top.path;
    return {
        schemaVersion: "store_taxonomy_v1",
        industry, category, subcategory,
        path: pathString(top.path),
        industries,
        industryCount: industries.length,
        brandModel: null,
        confidence: ranked.length && top.score >= 6 ? "medium" : "low",
        source: "keywords",
    };
};

const sampleSpread = (arr, n) => {
    const a = (arr || []).filter(Boolean);
    if (a.length <= n) return a;
    const out = [];
    const stride = a.length / n;
    for (let i = 0; i < n; i++) out.push(a[Math.floor(i * stride)]);
    return [...new Set(out)];
};

/**
 * Classify a store into the taxonomy. AI picks from the fixed list (and reads
 * whether the titles are one brand or many); the answer is validated against
 * TAXONOMY and falls back to the keyword scorer on any error / invalid path.
 *
 * @param {object} p
 * @param {string} p.domain
 * @param {string[]} [p.categories]  collection / nav category names
 * @param {string[]} [p.productTypes]
 * @param {string[]} [p.titles]      product titles
 * @param {string[]} [p.vendors]     top vendor names (Shopify)
 * @param {(prompt:string, opts:object)=>Promise<string>} [p.llm]  injected for tests
 * @param {(text:string)=>any} [p.parseJson]
 */
export const classifyTaxonomy = async ({ domain, categories = [], productTypes = [], titles = [], vendors = [], llm, parseJson } = {}) => {
    const kw = taxonomyFromKeywords({ categories, productTypes, titles });
    if (!llm || (!categories.length && !titles.length && !productTypes.length)) return kw;

    const options = allPaths().map((p) => `- ${p.join(" > ")}`).join("\n");
    const prompt = `You classify an online store into a FIXED taxonomy. Pick ONLY from the list.

Store: ${domain}
Categories: ${sampleSpread(categories, 25).join(", ") || "unknown"}
Product types: ${sampleSpread(productTypes, 15).join(", ") || "unknown"}
Sample product titles: ${sampleSpread(titles, 25).join(" | ") || "unknown"}
Vendors on products: ${vendors.slice(0, 10).join(", ") || "unknown"}

Taxonomy (Industry > Category > Subcategory):
${options}

Return:
- "primary": the single best path for what this store MAINLY sells.
- "industries": every Industry the store sells a meaningful share of (most important first).
- "brandModel": "single_brand" if the products are the store's OWN brand, "multi_brand" if titles/vendors show many different brands.

Reply ONLY JSON: {"primary":{"industry":"...","category":"...","subcategory":"..."},"industries":["..."],"brandModel":"single_brand|multi_brand"}`;

    try {
        const raw = await llm(prompt, { maxTokens: 300 });
        const parsed = parseJson ? parseJson(raw) : JSON.parse(raw);
        const p = parsed?.primary || {};
        if (!isValidPath(p.industry, p.category, p.subcategory)) throw new Error(`invalid path ${JSON.stringify(p)}`);
        let industries = (Array.isArray(parsed.industries) ? parsed.industries : [])
            .filter((i) => INDUSTRIES.includes(i));
        if (!industries.includes(p.industry)) industries = [p.industry, ...industries];
        industries = [...new Set(industries)];
        const brandModel = ["single_brand", "multi_brand"].includes(parsed.brandModel) ? parsed.brandModel : null;
        return {
            schemaVersion: "store_taxonomy_v1",
            industry: p.industry,
            category: p.category,
            subcategory: p.subcategory,
            path: pathString([p.industry, p.category, p.subcategory]),
            industries,
            industryCount: industries.length,
            brandModel,
            // Agreement with the keyword read raises confidence.
            confidence: kw.industry === p.industry ? "high" : "medium",
            source: "ai",
        };
    } catch (err) {
        console.warn("taxonomy AI classification failed, using keywords:", err?.message || err);
        return kw;
    }
};

/** Same industry → comparable; same category → closer still. 0..1 */
export const taxonomySimilarity = (a, b) => {
    if (!a?.industry || !b?.industry) return null;
    if (a.industry !== b.industry) {
        const shared = (a.industries || []).some((i) => (b.industries || []).includes(i));
        return shared ? 0.35 : 0;
    }
    if (a.category !== b.category) return 0.6;
    return a.subcategory === b.subcategory ? 1 : 0.85;
};

export default { TAXONOMY, allPaths, keywordClassify, taxonomyFromKeywords, classifyTaxonomy, taxonomySimilarity, isValidPath };
