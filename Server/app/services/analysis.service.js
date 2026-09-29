import Analysis from "../models/analysis.js";

const createAnalysis = async (workspaceId, competitors, data) => {
    // Upsert per competitor so re-running a competitor's analysis (on a
    // monitoring change) REPLACES its analysis instead of piling up duplicates.
    const payload = {
        workspaceId,
        competitors: {
            ownerId: competitors.ownerId,
            competitorId: competitors.competitorId,
        },
        data: {
            comparison: data?.comparison || {},
            payload: data?.payload || {},
            result: data?.result || null,
        },
    };

    await Analysis.findOneAndUpdate(
        { "competitors.competitorId": competitors.competitorId },
        payload,
        { upsert: true, new: true, setDefaultsOnInsert: true }
    );
}

const deleteAnalysis = async (analysisId) => {
    try {
        const deletedAnalysis = await Analysis.findByIdAndDelete(analysisId);
        if (!deletedAnalysis) {
            throw new Error("Analysis not found");
        }
        return deletedAnalysis;
    }
    catch (error) {
        throw new Error(`Error deleting analysis: ${error.message}`);
    }
};

const getAnalysisByWorkspaceId = async (workspaceId) => {
    try {
        const analysis = await Analysis.find({ workspaceId });
        return analysis;
    } catch (error) {
        throw new Error(`Error fetching analysis: ${error.message}`);
    }
};

const getAnalysisById = async (analysisId) => {
    try {
        const analysis = await Analysis.findById(analysisId);
        if (!analysis) {
            throw new Error("Analysis not found");
        }
        return analysis;
    } catch (error) {   
        throw new Error(`Error fetching analysis: ${error.message}`);
    }
}

const getAnalysisByCompetitorId = async (competitorId) => {
    try {
        const analysis = await Analysis.findOne({ "competitors.competitorId": competitorId });
        return analysis;
    } catch (error) {
        throw new Error(`Error fetching analysis: ${error.message}`);
    }
}

const deleteAnalysisByWorkspaceId = async (workspaceId) => {
    try {
        const deletedAnalysis = await Analysis.deleteMany({ workspaceId });
        return deletedAnalysis;
    } catch (error) {
        throw new Error(`Error deleting analysis: ${error.message}`);
    }
};

export { createAnalysis, deleteAnalysis, getAnalysisByWorkspaceId, deleteAnalysisByWorkspaceId, getAnalysisById, getAnalysisByCompetitorId };