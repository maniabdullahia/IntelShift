import api from "./api";
import Swal from "../components/shared/Alert";

/**
 * Create a competitor record for a workspace.
 *
 * @param {object} params - Competitor payload.
 * @param {string} params.url - Competitor website URL.
 * @param {string} params.role - Competitor role or category.
 * @param {string|number} params.workspaceId - Workspace identifier.
 * @param {Array<string|number>} params.selectedPages - Page identifiers to track.
 * @param {string} params.name - Competitor name.
 * @returns {Promise<any>} API response data for the created competitor.
 */
const createCompetitor = async ({ url, role, workspaceId, selectedPages, name, pagePairs }) => {
    try {
        const response = await api.post("/competitor", { url, role, workspaceId, selectedPages, name, pagePairs });
        Swal.fire({
            icon: 'success',
            title: 'Competitor staged',
            text: response.data?.message || "It'll be analyzed on your next monitoring run.",
        });
        return response.data;
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Error Adding Competitor',
            text: error.response?.data?.message || 'An unexpected error occurred while adding the competitor.',
        });
        const e = new Error(error.response?.data?.message || "Error creating competitor");
        e.code = error.response?.data?.code;
        throw e;
    }
};

/**
 * Fetch a competitor for a workspace.
 *
 * @param {object} params - Lookup payload.
 * @param {string|number} params.workspaceId - Workspace identifier.
 * @param {string|number} params.competitorId - Competitor identifier.
 * @returns {Promise<any>} API response data for the requested competitor.
 */
const getCompetitor = async ({ workspaceId, competitorId }) => {
    try {
        const response = await api.get("/competitor", { workspaceId, competitorId });
        return response.data;
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Error Fetching Competitor',
            text: error.response?.data?.message || 'An unexpected error occurred while fetching the competitor.',
        });
        throw new Error(error.response?.data?.message || "Error fetching competitor");
    }
}

/**
 * [Deprecated] Update an existing competitor record.  This function is not designed for Developer use, but rather for internal use by the application when modifying competitor data.
 *
 * @param {object} data - Updated competitor payload.
 * @returns {Promise<any>} API response data for the updated competitor.
 */
const updateCompetitor = async (data) => {
    try {
        const response = await api.put("/competitor", data);
        return response.data;
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Error Updating Competitor',
            text: error.response?.data?.message || 'An unexpected error occurred while updating the competitor.',
        });
        throw new Error(error.response?.data?.message || "Error updating competitor");
    }
}

/**
 * Delete a competitor from a workspace.
 *
 * @param {object} params - Deletion payload.
 * @param {string|number} params.workspaceId - Workspace identifier.
 * @param {string|number} params.competitorId - Competitor identifier.
 * @returns {Promise<any>} API response data for the deletion request.
 */
const deleteCompetitor = async ({ workspaceId, competitorId }) => {
    try {
        console.log("Deleting competitor with ID:", competitorId, "from workspace ID:", workspaceId);
        const response = await api.delete("/competitor", {
            data: { workspaceId, competitorId }
        });
        Swal.fire({
            icon: 'success',
            title: response.data?.dropped ? 'Competitor removed' : 'Marked for removal',
            text: response.data?.message || 'It stops being tracked at your next monitoring run.',
        });
        return response.data;
    } catch (error) {
        Swal.fire({
            icon: 'error',
            title: 'Error Deleting Competitor',
            text: error.response?.data?.message || 'An unexpected error occurred while deleting the competitor.',
        });
        const e = new Error(error.response?.data?.message || "Error deleting competitor");
        e.code = error.response?.data?.code;
        throw e;
    }
}

/** Cancel a staged competitor add/remove. */
const undoCompetitorChange = async ({ competitorId }) => {
    const response = await api.post("/competitor/undo", { competitorId });
    return response.data;
};

export {
    createCompetitor,
    getCompetitor,
    updateCompetitor,
    deleteCompetitor,
    undoCompetitorChange
};
