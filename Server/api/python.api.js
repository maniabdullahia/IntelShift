import axios from "axios";

/*
|--------------------------------------------------------------------------
| PYTHON API CLIENT
|--------------------------------------------------------------------------
| Lazy-loaded to avoid undefined env issues in workers
*/
function getPythonApi() {
  const PYTHON_API_URL = process.env.PYTHON_SERVER_URL;

  if (!PYTHON_API_URL) {
    throw new Error(
      "❌ PYTHON_SERVER_URL is not defined in environment variables"
    );
  }

  return axios.create({
    baseURL: PYTHON_API_URL,
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