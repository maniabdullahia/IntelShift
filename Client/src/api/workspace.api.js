import api from "./api";
import Swal from "../components/shared/Alert";

/**
 * Create a new workspace.
 *
 * @param {string} name - Workspace name.
 * @param {string} url - Workspace URL.
 * @param {string} industry - Workspace industry.
 * @param {array} selectedPages - List of selected pages for competitor analysis.
 * @returns {Promise<any>} API response data for the created workspace.
 */
const createWorkspace = async (name, url, industry, selectedPages) => {
    try {
        const response = await api.post("/workspace", { name, url, industry, selectedPages });
        Swal.fire({
            icon: "success",
            title: "Workspace Created",
            text: "Your workspace has been created successfully!",
        });
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: "error",
                title: "Invalid Input",
                text: "Please check your input and try again.",
            });
        }
        else if (status === 409) {
            Swal.fire({
                icon: "error",
                title: "Workspace Already Exists",
                text: "A workspace with this name already exists. Please choose a different name.",
            });
        } else {
            console.error("Failed to create workspace:", error);
            Swal.fire({
                icon: "error",
                title: "Creation Failed",
                text: "An error occurred while creating the workspace. Please try again.",
            });
            throw error;
        }
    };
}

/**
 * Fetch all workspaces.
 *
 * @returns {Promise<any>} API response data for the workspace list.
 */
const getWorkspace = async () => {
    try {
        const response = await api.get("/workspace");
        console.log("Fetched workspace data:", response.data);
        return response.data;
    } catch (error) {
        if (error.status == 404) {
            return null;
        }
        throw error;
    }

};

/**
 * Update an existing workspace.
 *
 * @param {object} data - Workspace update payload.
 * @returns {Promise<any>} API response data for the updated workspace.
 */
const updateWorkspace = async (data) => {
    const response = await api.put("/workspace", data);
    return response.data;
};

/**
 * Delete the current workspace.
 *
 * @returns {Promise<any>} API response data for the deletion request.
 */
const deleteWorkspace = async () => {
    const response = await api.delete("/workspace");
    return response.data;
};

/**
 * Create a new workspace with a competitor.
 *
 * @param {*} name "Name of the workspace"
 * @param {*} url "URL of the workspace"
 * @param {*} industry "Industry of the workspace"
 * @param {*} selectedPages "List of selected pages for competitor analysis"
 * @param {*} competitorName "Name of the competitor"
 * @param {*} competitorUrl "URL of the competitor"
 * @param {*} competitorSelectedPages "List of selected pages for the competitor"
 * @return {*} 
 */
const createWorkspaceWithCompetitor = async (name, url, industry, selectedPages, competitorName, competitorUrl, competitorSelectedPages) => {
    try {
        const response = await api.post("/workspace-with-competitor", { name, url, industry, selectedPages, competitorName, competitorUrl, competitorSelectedPages });
        Swal.fire({
            icon: "success",
            title: "Workspace Created",
            text: "Your workspace and competitor have been created successfully!",
        });
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: "error",
                title: "Invalid Input",
                text: "Please check your input and try again.",
            });
        }
        else if (status === 409) {
            Swal.fire({
                icon: "error",
                title: "Workspace Already Exists",
                text: "A workspace with this name already exists. Please choose a different name.",
            });
        }
        else {
            console.error("Failed to create workspace with competitor:", error);
            Swal.fire({
                icon: "error",
                title: "Creation Failed",
                text: "An error occurred while creating the workspace and competitor. Please try again.",
            });
            throw error;
        }
    };
}

/**
 * 
 *
 * @return {*} 
 */
const markIntroCompleted = async () => {
    try {
        const response = await api.post("/workspace/mark-intro-completed");
        return response.data;
    } catch (error) {
        console.error("Failed to mark intro as completed:", error);
        Swal.fire({
            icon: "error",
            title: "Action Failed",
            text: "An error occurred while marking the introduction as completed. Please try again.",
        });
        throw error;
    }
};

const createWorkspaceWithCompetitors = async (payload) => {
    try {
        const response = await api.post("/workspace-with-competitors", payload);
        Swal.fire({
            icon: "success",
            title: "Workspace Created",
            text: "Your workspace and competitors have been created successfully!",
        });
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 400) {
            Swal.fire({
                icon: "error",
                title: "Invalid Input",
                text: "Please check your input and try again.",
            });
        }
        else if (status === 409) {
            Swal.fire({
                icon: "error",
                title: "Workspace Already Exists",
                text: "A workspace with this name already exists. Please choose a different name.",
            });
        }
        else {
            console.error("Failed to create workspace with competitors:", error);
            Swal.fire({
                icon: "error",
                title: "Creation Failed",
                text: "An error occurred while creating the workspace and competitors. Please try again.",
            });
            throw error;
        }
    }
}

/**
 * Capture-first creation: send URLs only (owner + competitors) + industry.
 * The server creates the workspace and every site with NO pages, then runs
 * breadth-only recon. Page selection + mapping happen later, in the workspace.
 *
 * @param {object} payload { workspaceName, url, industry, currency, region, storeUrl, competitors: [{name,url,region,storeUrl,currency}] }
 */
const createWorkspaceRecon = async (payload) => {
    try {
        const response = await api.post("/workspace-recon", payload);
        Swal.fire({
            icon: "success",
            title: "Workspace created",
            text: "We're capturing each site now — you'll pick what to track next.",
        });
        return response.data;
    } catch (error) {
        const status = error.response?.status;
        if (status === 409) {
            Swal.fire({
                icon: "error",
                title: "Workspace already exists",
                text: "You already have a workspace. Remove it first to start over.",
            });
        } else if (status === 400) {
            Swal.fire({
                icon: "error",
                title: "Missing information",
                text: error.response?.data?.message || "Please provide your site, industry and at least one competitor.",
            });
        } else {
            console.error("Failed to create workspace (recon):", error);
            Swal.fire({
                icon: "error",
                title: "Creation failed",
                text: "An error occurred while creating the workspace. Please try again.",
            });
        }
        throw error;
    }
};

// Capture-first: fetch the recon we captured (collections + homepage summary per
// site) to populate the in-workspace selection panel.
const getWorkspaceRecon = async () => {
    const response = await api.get("/workspace/recon");
    return response.data;
};

// Recon-shape collections for an arbitrary store URL (used by the add-competitor
// mapping panel to show the same picker as onboarding, before the competitor exists).
const previewCollections = async (url) => {
    const response = await api.post("/workspace/preview-collections", { url });
    return response.data;
};

// Capture-first: auto-save the in-progress picks so a logout/refresh keeps them.
const saveSelectionDraft = async (draft) => {
    const response = await api.post("/workspace/selection-draft", { draft });
    return response.data;
};

// Capture-first: commit the user's page picks + competitor mappings. Creates the
// tracked pages, advances the workspace to "analyzing" and starts the deep crawl.
const commitSelection = async (payload) => {
    const response = await api.post("/workspace/commit-selection", payload);
    return response.data;
};

// Capture-first: swap a poor-fit competitor for a new URL and re-capture it.
const replaceCompetitor = async (competitorId, url) => {
    const response = await api.post("/workspace/replace-competitor", { competitorId, url });
    return response.data;
};

const getAnalysis = async (analysisId) => {
    try {
        const response = await api.get(`/analysis/${analysisId}`);
        return response.data;
    } catch (error) {
        console.error("Failed to fetch analysis:", error);
        Swal.fire({
            icon: "error",
            title: "Fetch Failed",
            text: "An error occurred while fetching the analysis. Please try again.",
        });
        throw error;
    }
};


const rescanWorkspace = async (workspaceId) => {
    const response = await api.get(`/workspace-rescan/${workspaceId}`);
    return response.data;
};

export {
    createWorkspace,
    getWorkspace,
    updateWorkspace,
    deleteWorkspace,
    createWorkspaceWithCompetitor,
    markIntroCompleted,
    createWorkspaceWithCompetitors,
    createWorkspaceRecon,
    getWorkspaceRecon,
    previewCollections,
    saveSelectionDraft,
    commitSelection,
    replaceCompetitor,
    getAnalysis,
    rescanWorkspace
};

