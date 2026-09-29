import axios from "axios";

const paddleApi = axios.create({
    baseURL: process.env.PADDLE_BASE_URL || "https://sandbox-api.paddle.com", // Use sandbox for testing, switch to https://api.paddle.com for production
    timeout: 10000,
});

paddleApi.interceptors.request.use((config) => {
    const apiKey = process.env.PADDLE_API_KEY;

    if (!apiKey) {
        throw new Error("PADDLE_API_KEY is missing");
    }

    config.headers.Authorization = `Bearer ${apiKey}`;
    config.headers["Content-Type"] = "application/json";

    return config;
});

paddleApi.interceptors.response.use(
    (response) => response,
    (error) => {
        console.error("Paddle API error:", error.response ? error.response.data : error.message);
        return Promise.reject(error);
    }
);

export default paddleApi;