import pythonApi from "../python.api.js";
import fs from "fs";

// How many representative products the comparison + AI evidence pack keep PER SITE.
// NOTE: Python treats this as a slice length, so 0 = "no products" (not unlimited).
// A small positive number gives the AI concrete price/product examples without
// bloating the payload. Internal only — never surfaced to users or tied to a plan.
const MAX_PRODUCTS_PER_SITE = Number(process.env.MAX_PRODUCTS_PER_SITE) || 12;

/**
 *
 * Compare owner site with multiple competitor sites
 * @param {*} owner Owner Site data (Object/json)
 * @param {*} competitors Array of competitor site data (Array of Object/json)
 * @return {*} 
 */
const compareSites = async (owner, ...competitors) => {
    try {
        const response = await pythonApi.post('/v1/compare-sites', {

            "userWebsite": owner,
            "competitors": [
                ...competitors
            ],
            "options": {
                "includeOpenAiEvidencePack": true,
                "includeProductDetails": true,
                "includePageContent": true,
                "includeSectionDetails": true,
                "includeOneToOneComparison": true,
                "maxProductsPerSite": MAX_PRODUCTS_PER_SITE,
                "maxSectionsPerSite": 0,
                "additionalProp1": {}
            },
            "additionalProp1": {}

        });
        fs.writeFileSync("comparison_response.json", JSON.stringify(response.data, null, 2));
        return response.data;
    } catch (error) {
        console.error('Error comparing sites:', error);
        throw error;
    }
}

/**
 *
 * One to one site comparison - used for comparing owner site with each competitor site 
 * @param {*} owner Owner Site data (Object/json)
 * @param {*} competitor Competitor site data (Object/json)
 * @return {*}
 */
const compareSite = async (owner, competitor) => {
    try {
        const response = await pythonApi.post('/v1/compare-one', {

            "userWebsite": owner,
            "competitorWebsite": competitor,
            "options": {
                "includeOpenAiEvidencePack": true,
                "includeProductDetails": true,
                "includePageContent": true,
                "includeSectionDetails": true,
                "includeOneToOneComparison": true,
                "maxProductsPerSite": MAX_PRODUCTS_PER_SITE,
                "maxSectionsPerSite": 0,
                "additionalProp1": {}

            }
        });

        return response.data;
    } catch (error) {
        console.error('Error comparing site:', error);
        throw error;
    }
}

export {
    compareSites,
    compareSite,
}