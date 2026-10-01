import axios from "axios";

/*
|--------------------------------------------------------------------------
| PYTHON API CLIENT
|--------------------------------------------------------------------------
| Lazy-loaded to avoid undefined env issues in workers
*/
function getPythonApi() {
  const PYTHON_API_URL = process.env.PYTHON_SERVER_URL;

  if (!PYTHON_API_URL || !/^https?:\/\//i.test(PYTHON_API_URL)) {
    throw new Error(
      `❌ PYTHON_SERVER_URL must be an absolute http(s) URL (e.g. http://localhost:8000/api), got: ${PYTHON_API_URL || "<unset>"}`
    );
  }

  // Service key for the Python API (python/api_security.py). Put the same value
  // in the Python service's COMPINTEL_SERVICE_KEYS so backend calls are
  // authenticated but never rate-limited. Unset = dev mode (Python auth off).
  const apiKey = process.env.PYTHON_API_KEY;

  return axios.create({
    baseURL: PYTHON_API_URL,
    headers: apiKey ? { "X-API-Key": apiKey } : {},
    // The site comparison (/compare-one) ships the FULL merged snapshot — a large
    // store (e.g. breakout, 1500+ products) is a ~6.6MB payload the Python side
    // needs well over a minute to crunch. 60s aborted it mid-flight, which is the
    // "report step failed / stuck at generating reports" symptom. Give it room;
    // tune via PYTHON_API_TIMEOUT_MS.
    timeout: Number(process.env.PYTHON_API_TIMEOUT_MS) || 300000, // 5 min
    maxContentLength: Infinity,
    maxBodyLength: Infinity,
  });
}

/*
|--------------------------------------------------------------------------
| EXPORT CLIENT INSTANCE (via getter)
|--------------------------------------------------------------------------
*/
const pythonApi = {
  post: (url, data, config) =>
    getPythonApi().post(url, data, config),

  get: (url, config) =>
    getPythonApi().get(url, config),

  put: (url, data, config) =>
    getPythonApi().put(url, data, config),

  delete: (url, config) =>
    getPythonApi().delete(url, config),
};

export default pythonApi;