import api from "./api";

const getUsers = async (page, limit) => {
    try {
        const response = await api.get(`/admin/users?page=${page}&limit=${limit}`);
        return response.data;
    }
    catch (error) {
        console.error('Error fetching users:', error.message);
    }
}

const getUserById = async (userId) => {
    try {
        const response = await api.get(`/admin/users/${userId}`);
        return response.data;
    } catch (error) {
        console.error('Error fetching user:', error.message);       
    }
}

export {
    getUsers,
    getUserById
}