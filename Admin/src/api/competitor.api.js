import api from "./api";

const getCompetitors = async (page, limit) => {
    try {
        const response = await api.get(`/admin/competitors?page=${page}&limit=${limit}`);
        console.log('API response for competitors:', response);
        return response.data;
    } catch (error) {
        console.error('Error fetching competitors:', error.message);
        throw error;
    }
}

export { getCompetitors };