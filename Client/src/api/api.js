import axios from "axios";
import useAuthStore from "../store/auth.store";
import useWorkspaceStore from "../store/workspace.store";

// Falls back to the local dev API (matches .env.development) when the env var is unset.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:3000/api";

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
});

// -----------------------------
// 1. REQUEST INTERCEPTOR
// Attach access token to every request
// -----------------------------
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// -----------------------------
// 2. RESPONSE INTERCEPTOR
// Handle expired access token → refresh flow
// -----------------------------
let isRefreshing = false;
let failedQueue = [];

const processQueue = (error, token = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve(token);
    }
  });

  failedQueue = [];
};

api.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config;
    const isRefreshCall = originalRequest?.url?.includes("/refresh-token");

    // If access token expired
    if (error.response?.status === 401 && originalRequest && !originalRequest._retry && !isRefreshCall) {
      if (isRefreshing) {
        // queue requests while refreshing
        return new Promise(function (resolve, reject) {
          failedQueue.push({ resolve, reject });
        })
          .then((token) => {
            originalRequest.headers.Authorization = "Bearer " + token;
            return api(originalRequest);
          })
          .catch((err) => {
            return Promise.reject(err);
          });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const res = await axios.post(
          `${BASE_URL}/refresh-token`,
          {},
          { withCredentials: true } // refresh token is expected in an HTTP-only cookie
        );
        console.log("🔴 Token refreshed successfully");

        const newAccessToken = res.data.accessToken;

        if (!newAccessToken) {
          throw new Error("Missing access token in refresh response");
        }

        // update Zustand store
        useAuthStore.getState().setToken(newAccessToken);

        processQueue(null, newAccessToken);

        originalRequest.headers.Authorization = "Bearer " + newAccessToken;

        return api(originalRequest);
      } catch (err) {
        processQueue(err, null);

        // logout user if refresh fails
        useAuthStore.getState().logout();
        useWorkspaceStore.getState().clearStorage();

        return Promise.reject(err);
      } finally {
        isRefreshing = false;
      }
    }

    // Read-only account (ended trial / inactive): the API refused a mutation.
    // Surface a single upgrade prompt rather than a raw error, so the whole app is
    // effectively read-only without disabling every button individually.
    if (error.response?.status === 403 && error.response?.data?.code === "READ_ONLY") {
      const d = error.response.data || {};
      try {
        const { default: Swal } = await import("../components/shared/Alert");
        Swal.fire({
          icon: "info",
          title: d.reason === "trial_expired" ? "Your free trial has ended" : "Subscription inactive",
          text: d.message || "Upgrade to make changes and resume monitoring.",
          showCancelButton: true,
          confirmButtonText: "Upgrade",
          cancelButtonText: "Not now",
        }).then((r) => {
          if (r?.isConfirmed) window.location.assign("/settings/billing");
        });
      } catch {
        /* Alert unavailable — still reject below */
      }
      return Promise.reject(error);
    }

    return Promise.reject(error);
  }
);

export default api;