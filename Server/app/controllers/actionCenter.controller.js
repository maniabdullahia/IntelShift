import { getActionCenter } from "../services/actionCenter.service.js";

// GET /action-center — outstanding setup to-dos for the current workspace
const actionCenter = async (req, res) => {
  try {
    const data = await getActionCenter(req.workspace);
    return res.json(data);
  } catch (error) {
    console.error("[ACTION CENTER ERROR]", error);
    return res.status(500).json({ message: error.message });
  }
};

export { actionCenter };
