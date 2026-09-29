import api from "./api";

const getJobs = async (page, limit) => {
    try {
        const response = await api.get(`/admin/jobs?page=${page}&limit=${limit}`);
        return response.data;
    }
    catch (error) {
        console.error('Error fetching jobs:', error.message);
        throw error;
    }
}

export { getJobs };