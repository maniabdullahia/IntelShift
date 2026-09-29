
import api from "./api.js";

const getPlans = async () => {
  try {
    const response = await api.get("/plans");
    return response.data;
  }
    catch (error) {
    console.error("Error fetching plans:", error);
    throw error;
  }
}



export { getPlans };