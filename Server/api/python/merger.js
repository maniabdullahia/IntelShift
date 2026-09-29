import pythonApi from "../python.api.js";

const mergeJson = async (...jsonData) => {
    try {
        const response = await pythonApi.post('/v1/merge-site', { pages: jsonData });
        return response.data;
    } catch (error) {
        console.error('Error merging JSON:', error);
        throw error;
    }
}

export {
    mergeJson,
}