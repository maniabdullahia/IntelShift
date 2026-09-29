import Workspace from "../models/workspace.js";

const workspaceMiddleware = async (req, res, next) => {
    try {
        const { id } = req.user;
        const workspace = await Workspace.findOne({ ownerId: id });
        if (!workspace) {
            return res.status(404).json({ message: "Invalid OR UnAuthorized Workspace." });
        }
        req.workspace = workspace;
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

const workspaceOwnershipMiddleware = async (req, res, next) => {
    try {
        const { id } = req.user;
        const workspace = await Workspace.findOne({ ownerId: id });
        if (!workspace) {
            return res.status(404).json({ message: "Invalid OR UnAuthorized Workspace." });
        }
        if (workspace.ownerId.toString() !== id) {
            return res.status(403).json({ message: "Forbidden: You do not have access to this workspace." });
        }
        req.workspace = workspace;
        next();
    } catch (error) {
        res.status(500).json({ message: error.message });
    }
}

export {
    workspaceMiddleware,
    workspaceOwnershipMiddleware
}