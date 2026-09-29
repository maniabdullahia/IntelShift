
import { collectionPageSchema, HomePageSchema, UniversalAnalyticsSchema, UniversalSchema, productSchema } from "./schema.js";
import puppeteer from "puppeteer";
import fs from "fs";
import OpenAI from "openai";
import dotenv from "dotenv";
import * as cheerio from "cheerio";
import axios from "axios";

import { recordAIUsage } from "../app/services/ai.service.js";

dotenv.config();
// A per-request timeout + bounded retries so a stalled AI call can NEVER hang a
// worker forever (the "stuck at generating reports" symptom). Applies to every
// OpenAI call in this module.
const client = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY,
    timeout: Number(process.env.AI_REQUEST_TIMEOUT_MS) || 300000,
    maxRetries: 2,
});

/*
| Largest HTML payload we send to the model. A full product / collection page can
| be enormous; sending it raw overflows the model's input limit, the call 400s,
| the analyzer returns null, and the page "fails". We'd rather send a lot (cost is
| acceptable) but stay under the limit — so cap generously and truncate the tail
| (headers/nav are already stripped upstream, so the top carries the real content).
| Tune via MAX_ANALYSIS_HTML_CHARS without a code change.
*/
const MAX_HTML_CHARS = Number(process.env.MAX_ANALYSIS_HTML_CHARS) || 180000;
const capHtml = (html) => {
    const s = (html ?? "").toString();
    return s.length > MAX_HTML_CHARS ? s.slice(0, MAX_HTML_CHARS) : s;
};

// Browser-like headers so bot-protected stores don't hand us a challenge page or
// a 403 on a plain request (the Python path already handles the hard cases).
const BROWSER_HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    Accept: "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
};

/*
| Single entry point for EVERY model call, so the whole analysis pipeline honours
| AI_PROVIDER (openai | claude) — not just the final report. Returns a uniform
| { output_text, usage } shape whichever provider runs. Set AI_PROVIDER=claude,
| ANTHROPIC_API_KEY and (optionally) ANTHROPIC_MODEL to run everything on Claude.
*/
const openaiResponses = client.responses; // captured so the switch can still reach the raw OpenAI call
async function modelCall({ input, max_tokens = 16384 } = {}) {
    const provider = (process.env.AI_PROVIDER || "openai").trim().toLowerCase();
    const requestTimeout = Number(process.env.AI_REQUEST_TIMEOUT_MS) || 300000;

    if (provider === "claude") {
        const { default: Anthropic } = await import("@anthropic-ai/sdk");
        const anthropic = new Anthropic({
            apiKey: process.env.ANTHROPIC_API_KEY,
            timeout: requestTimeout,
            maxRetries: 2,
        });
        const msg = await anthropic.messages.create({
            model: process.env.ANTHROPIC_MODEL || "claude-sonnet-5",
            max_tokens,
            messages: [{ role: "user", content: input }],
        });
        let text = (msg.content || []).map((b) => b.text || "").join("").trim();
        // Strip ```json fences if the model wrapped its JSON in a code block.
        text = text.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/i, "").trim();
        const tokens = (msg.usage?.input_tokens || 0) + (msg.usage?.output_tokens || 0);
        return { output_text: text, usage: { total_tokens: tokens }, model: msg.model, provider: "claude" };
    }

    const response = await openaiResponses.create({
        model: process.env.OPENAI_MODEL || "gpt-5.2",
        input,
    });
    return {
        output_text: response.output_text,
        usage: response.usage,
        model: response.model,
        provider: "openai",
    };
}

/**
 *
 *
 * @export
 * @param {*} client
 * @param {*} url
 * @return {*}
 */
export async function pageClassifier(client, url) {
    try {
        const response = await modelCall({
            model: "gpt-5.2",
            input: `You are a page classifier. Classify the following page into a category and confident score. Output should be in JSON format. {page_category: string, page_type: string(single keyword), page_description: string, confidence_score: number}. Input URL is ${url},. Output should be in JSON with no additional text.'`,
        });
        return response.output_text;
    } catch (error) {
        console.error("Error classifying page:", error);
    }
}

function isValidJson(jsonString) {
    try {
        JSON.parse(jsonString);
        return true;
    }
    catch (error) {
        return false;
    }
}

async function generateAiStats(analysisResult) {
    const stats = {
        tokensUsed: analysisResult.usage.total_tokens,
        cost: (analysisResult.usage.total_tokens / 1000) * 0.002, // Assuming $0.002 per 1K tokens
        isValidJson: isValidJson(analysisResult.output_text),
        failure: analysisResult?.status === "failed" ? failureCount++ : failureCount,
    }

    await recordAIUsage(null, stats.tokensUsed, stats.cost, stats.isValidJson, stats.failure);
}

/**
 *
 *
 * @export
 * @param {*} client
 * @param {*} htmlContent
 * @return {*}
 */
export async function HTMLPageClassifer(client, htmlContent) {
    try {
        const response = await modelCall({
            model: "gpt-5.2",
            input: `You are a page classifier. Classify the following HTML content into a category and confident score. Output should be in JSON format. {page_category: string, page_type: string(single keyword), page_description: string, confidence_score: number}. Input HTML content is ${htmlContent.toString().substring(0, 10000)}, Output should be in JSON with no additional text.'`,
        });
        return response.output_text;
    } catch (error) {
        console.error("Error classifying page:", error);
    }
}

/**
 * Crawls a web page and retrieves its HTML content.
 * @export
 * @param {*} axios Instance of axios to make HTTP requests
 * @param {*} url URL of the web page to crawl
 * @return {*} HTML content of the crawled web page
 */
export async function crawlWebPage(axios, url) {
    const response = await axios.get(url, {
        timeout: 25000,
        maxRedirects: 5,
        headers: BROWSER_HEADERS,
    });
    return response.data;
}

/**
 *
 *
 * @export
 * @param {*} $ Cheerio Handler
 * @return {*} Cleaned HTML, Removes Tags/Classes like [ header, footer, .header, .footer, nav, .navbar, link, script, noscript, .banner, .hero, svg, .icon]
 */
export async function cleanWebPage($) {
    const text = await $(
        "header, footer, .header, .footer, nav, .navbar, link, script, noscript, .banner, .hero, svg, .icon, style",
    ).remove();
    // fs.writeFileSync("output/cleaned_page.html", $.html());
    // console.log('Cleaned HTML content saved to output/cleaned_page.html', cleaned_Text.toString().substring(0, 500));
    return $.html();
}

/**
 *
 *
 * @export
 * @param {*} client
 * @param {*} htmlContent
 * @param {*} pageType
 * @return {*}
 */
export async function AnalyzeCollectionPage(client, htmlContent, pageType) {
    try {
        const response = await modelCall({
            model: "gpt-5.2",
            input: `You are a ${pageType} page analyzer. Analyze the following HTML content based on the page type and extract relevant information. Output should be in JSON format according to the schema provided. Input HTML content is ${capHtml(htmlContent)}, Page Type is ${pageType}. Output should be in JSON with no additional text. Schema: ${JSON.stringify(collectionPageSchema)} the content in schema is only for example and you should follow the structure of the schema but extract information based on the input HTML content. If certain fields are not available in the HTML content, you can leave them as null or empty arrays as appropriate. Focus on extracting accurate and relevant information based on the page type and the provided HTML content.'`,
        });

        return response;
    } catch (error) {
        console.error("Error analyzing page:", error);
        return null;
    }
}

export async function AnalyzePageWithURL(client, url, pageType) {
    try {
        const response = await modelCall({
            model: "gpt-5.2",
            input: `You are a ${pageType} page analyzer. Analyze the following URL and make sure the output response should match this schema ${JSON.stringify(collectionPageSchema)} the content in schema is only for example and you should follow the structure of the schema but extract information based on the input URL. If certain fields are not available based on the URL content, you can leave them as null or empty arrays as appropriate. Focus on extracting accurate and relevant information based on the page type and the provided URL.' Input URL is ${url}. Output should be in JSON with no additional text.'`,
        });
        // fs.writeFileSync(
        //     "output/analyzed_data_with_url.json",
        //     response.output_text,
        // );


        return response;
    } catch (error) {
        console.error("Error analyzing page with URL:", error);
        return null;
    }
}

export async function productCheerioAnalyzer(client, htmlContent) {
    try {
        const schemaBlueprint = JSON.stringify(productSchema, null, 2);
        console.time("Cheerio Analysis Time");

        // 6️⃣ Send to GPT
        const response = await modelCall({
            model: "gpt-5.2",
            input: `
You are a product page analyzer.

Analyze the given HTML content and extract detailed information about the products listed on the page.

IMPORTANT:
- Some product information may be located inside tab sections such as Security, Safety, Instructions, Specifications, etc.
- These sections may be hidden using CSS or loaded dynamically.
- You must extract content from ALL sections of the HTML, including hidden/tabbed sections.

Output must be in JSON format following this structure:
${schemaBlueprint}

If any information is missing, use:
- null for strings/numbers
- empty arrays for lists

Do not include any additional explanation.

HTML Content:
${capHtml(htmlContent)}
`,
        });
        console.timeEnd("Cheerio Analysis Time");


        return response;
    } catch (error) {
        console.error("Error analyzing products:", error);
    }
}

export async function productAnalyzer(client, url) {
    let browser;

    const domain = new URL(url).hostname.split(".")[0];
    try {
        console.time("Puppeteer Analysis Time");
        // 1️⃣ Launch browser
        browser = await puppeteer.launch({
            headless: "new",
            args: ["--no-sandbox", "--disable-setuid-sandbox"],
            timeout: 60000, // 60 seconds timeout for launching
        });

        const page = await browser.newPage();

        // 2️⃣ Load page and wait for network to be idle
        await page.goto(url, { waitUntil: "networkidle2" });

        // 3️⃣ Click all possible tabs/buttons to load hidden content
        const tabSelectors = [
            '[role="tab"]',
            ".tab",
            ".tabs button",
            ".nav-tabs button",
            'button[data-toggle="tab"]',
        ];

        for (const selector of tabSelectors) {
            const tabs = await page.$$(selector);

            for (const tab of tabs) {
                try {
                    await tab.click();
                    await page.waitForTimeout(500); // allow dynamic content to load
                } catch (err) {
                    // ignore click errors
                }
            }
        }

        // 4️⃣ Get fully rendered HTML
        const fullHTML = await page.content();

        await browser.close();

        // 5️⃣ Prepare schema
        const schemaBlueprint = JSON.stringify(productSchema, null, 2);

        // 6️⃣ Send to GPT
        const response = await modelCall({
            model: "gpt-5.2",
            input: `
        You are a product page analyzer.

        Analyze the given HTML content and extract detailed information about the products listed on the page.

        IMPORTANT:
        - Some product information may be located inside tab sections such as Security, Safety, Instructions, Specifications, etc.
        - These sections may be hidden using CSS or loaded dynamically.
        - You must extract content from ALL sections of the HTML, including hidden/tabbed sections.

        Output must be in JSON format following this structure:
        ${schemaBlueprint}

        If any information is missing, use:
        - null for strings/numbers
        - empty arrays for lists

        Do not include any additional explanation.

        HTML Content:
        ${capHtml(fullHTML)}
      `,
        });


        console.timeEnd("Puppeteer Analysis Time");

        // fs.writeFileSync(`./output/${folderName}/${fileName}_analysis.json`, response.output_text);

        return response;
    } catch (error) {
        console.error("Error analyzing products:", error);
    } finally {
        if (browser) await browser.close();
    }
}

export async function AnalyzeHomePage(client, htmlContent, pageType) {
    try {
        const prompt = `
            You are an HomePage Analyzer. Analyze the given HTML content and extract only the store information. 
            Output must strictly follow the JSON schema provided. If certain fields are not available, return null. 
            Output only JSON, no extra text. Here is the JSON schema you must follow:
            ${JSON.stringify(HomePageSchema, null, 2)} and here is the HTML content you need to analyze:
            ${capHtml(htmlContent)}
        `;

        const response = await modelCall({
            model: "gpt-5.2",
            input: prompt,
        });

        // fs.writeFileSync("output/homepage_analysis.json", response.output_text);
        return response;
    } catch (error) {
        console.error("Error analyzing home page:", error);
        return null;
    }
}

export async function AnalyzeUniversalPage(client, htmlContent) {
    try {
        const response = await modelCall({
            model: "gpt-5.2",
            input: `You are an Homepage Analyzer. Analyze the given web page and extract all the information in the JSON format.
            Give me all the content not UI elements nor UI content. If certain fields are not available, return null.
            HTML Content:
            ${capHtml(htmlContent)}

            Return only JSON with no additional text.
            `,
        });

        // fs.writeFileSync(`./output/${folderName}/${fileName}`, response.output_text);
        return response;
    } catch (error) {
        console.error("Error analyzing home page with URL:", error);
        return null;
    }
}

export async function smartMerge(target, source) {
    // If both are arrays → merge
    if (Array.isArray(target) && Array.isArray(source)) {
        return [...target, ...source];
    }

    // If both are objects → merge recursively
    if (
        typeof target === "object" &&
        typeof source === "object" &&
        target !== null &&
        source !== null &&
        !Array.isArray(target) &&
        !Array.isArray(source)
    ) {
        const result = { ...target };

        for (const key of Object.keys(source)) {
            if (key in result) {
                result[key] = smartMerge(result[key], source[key]);
            } else {
                result[key] = source[key];
            }
        }

        return result;
    }

    // If different types OR primitive → convert to array (preserve both)
    if (target !== source) {
        return [target, source];
    }

    return target;
}

export async function mergeJsonFiles(folder, files, outputFile) {
    try {
        let count = 1;
        let mergedData = {};

        // console.log("Merging files:", files);
        for (const file of files) {
            // console.log(`Processing file: ${file}`);
            const filePath = `${folder}/${file}`;
            if (fs.existsSync(filePath)) {
                // console.log(`Reading file: ${filePath}`);
                const data = await JSON.parse(fs.readFileSync(filePath, "utf-8"));
                // console.log(`🔴 File Data `, data)
                console.log(`🔴 Merging ${folder} file ${count}: ${file}`);
                mergedData = smartMerge(mergedData, data);
                // Object.assign(mergedData, data);
                count++;
            }
        }

        fs.writeFileSync(outputFile, JSON.stringify(mergedData, null, 2));

        // console.log("✅ Files merged successfully into:", outputFile);
        return mergedData;
    } catch (error) {
        console.error("Error merging files:", error);
    }
}

export async function compareAnalysis(aiPayload) {
    try {

        // Cap the evidence blob so a large store (many pages × competitors) can't
        // overflow the model's input limit and 400 the whole report. Generous —
        // the insights payload is far more compact than raw HTML.
        const MAX_PAYLOAD_CHARS = Number(process.env.MAX_AI_PAYLOAD_CHARS) || 500000;
        const evidence = JSON.stringify(aiPayload);
        const cappedEvidence =
            evidence.length > MAX_PAYLOAD_CHARS ? evidence.slice(0, MAX_PAYLOAD_CHARS) : evidence;

        const prompt = `
            You are a competitor intelligence analyst.
            Use ONLY the provided JSON evidence.
            Return ONLY valid JSON — no prose, no markdown fences.

            Be concise so the response is COMPLETE valid JSON, not truncated:
            keep every text field short, cap each array to the 5–8 most important
            items, and never echo the raw evidence verbatim.

            Comparison JSON:
            ${cappedEvidence}
        `;

        // A full competitor report can exceed 16k output tokens on dense catalogs
        // (Cougar truncated mid-JSON at the old 16k cap). Give it headroom — the
        // conciseness directive above keeps most reports well under this — and let
        // it be tuned via AI_MAX_OUTPUT_TOKENS. Provider is chosen inside modelCall.
        const maxOutputTokens = Number(process.env.AI_MAX_OUTPUT_TOKENS) || 20000;
        const response = await modelCall({ input: prompt, max_tokens: maxOutputTokens });

        if (!response?.output_text) {
            throw new Error("AI returned empty output_text");
        }
        console.log(`🧠 [insights] provider=${response.provider} model=${response.model}`);

        return response;

    } catch (error) {

        console.error(
            "Error comparing analyses:",
            error
        );

        return {
            error: true,
            message: error.message,
        };
    }
}

export async function AnalyzePage(pageType, client, cleanedContent, Url) {

    if (pageType === "collection" || pageType === "category") {
        return await AnalyzeCollectionPage(client, cleanedContent, pageType);
    } else if (pageType === "product" || pageType === "product_detail") {
        return await productAnalyzer(client, Url);
    } else {
        console.log(`No specific analyzer for page type "${pageType}". Using universal analyzer.`);
        return await AnalyzeUniversalPage(client, cleanedContent);
    }
}

export async function AnalyzeURL(url) {

    // const domain = new URL(url).hostname.split(".")[0];
    // const lastSegment = url.split("/").filter(Boolean).slice(-1)[0];
    // const fileName = `${domain}_${lastSegment}_analysis.json`;
    // fs.mkdirSync(`./output/${domain}`, { recursive: true });

    // console.log(`Folder name: ${domain}, File name: ${fileName}`);

    const crawledContent = await crawlWebPage(axios, url);
    const $ = cheerio.load(crawledContent);
    const cleanedContent = await cleanWebPage($);
    const htmlPageCategory = await HTMLPageClassifer(client, cleanedContent);
    // The classifier can return undefined (its own error is swallowed). Don't let
    // a JSON.parse blow up the whole page — fall back to the universal analyzer.
    let page_type = "universal";
    try {
        page_type = JSON.parse(htmlPageCategory)?.page_type || page_type;
    } catch {
        /* keep the universal fallback */
    }
    const analyzedData = await AnalyzePage(page_type, client, cleanedContent, url);
    // console.log('Analyzed Data => ', analyzedData);
    return analyzedData;

}

export async function Analyze(urls) {
    // for (let url of urls) {
    //   if(url.includes("www.")){
    //     url = url.replace("www.", "");
    //   }
    //   console.log(`Analyzing URL: ${url}`);
    //   await AnalyzeURL(url);
    // }

    let competitors = fs.readdirSync("./output")
    competitors = competitors.filter(competitors => competitors !== "Comparisons");
    console.log("Competitors found for merging:", competitors);
    for (const competitor of competitors) {
        const competitorPath = `./output/${competitor}`;
        if (fs.lstatSync(competitorPath).isDirectory()) {
            const files = fs.readdirSync(competitorPath).filter(file => file.endsWith("_analysis.json"));
            await mergeJsonFiles(competitorPath, files, `./output/${competitor}/${competitor}_final_merged_analysis.json`);
        }
    }

    await compareAnalysis(client);
}
