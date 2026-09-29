import api from "./api";

const getWorkspaces = async (page, limit) => {
    try {
        const response = await api.get(`/admin/workspaces?page=${page}&limit=${limit}`);
        return response.data;
    } catch (error) {
        console.error('Error fetching workspaces:', error.message);
    }
}

const deleteWorkspace = async (workspaceId) => {
    try {
        const response = await api.delete(`/admin/workspaces/${workspaceId}`);
        return response.data;
    } catch (error) {
        console.error('Error deleting workspace:', error.message);
    }
}

const getWorkspaceDetails = async (workspaceId) => {
    try {
        const response = await api.get(`/admin/workspaces/${workspaceId}`);
        return response.data;
    } catch (error) {
        console.error('Error fetching workspace details:', error.message);
    }
}



export {
    getWorkspaces,
    deleteWorkspace,
    getWorkspaceDetails,
}