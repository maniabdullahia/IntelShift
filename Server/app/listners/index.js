
import registerAnalysisListeners from "./analysis.listener.js";
import registerPageListeners from "./page.listener.js";
import registerCompetitorListeners from "./competitor.listener.js";
import registerWorkspaceListeners from "./workspace.listener.js";

function initializeAppListeners() {
    registerAnalysisListeners();
    registerPageListeners();
    registerCompetitorListeners();
    registerWorkspaceListeners();
}

export default initializeAppListeners;