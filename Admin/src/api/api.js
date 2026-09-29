import axios from 'axios';



const api = axios.create({
    baseURL: `${import.meta.env.VITE_SERVER_URL}/api`,

})

api.interceptors.request.use((config) => {
    const token = localStorage.getItem('auth-storage') ? JSON.parse(localStorage.getItem('auth-storage')).token : null;
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }

    return config;
}, (error) => {
    return Promise.reject(error);
});

api.interceptors.response.use((response) => {
    return response;
})

export default api;