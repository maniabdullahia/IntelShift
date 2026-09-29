import pythonApi from "../python.api.js";


const detectSnapshotChanges = async (oldSnapshot, newSnapshot) => {
    try {
        const response = await pythonApi.post('/v1/diff-snapshots', {
            "previousSnapshot": oldSnapshot,
            "currentSnapshot": newSnapshot,
            "settings": { "priceChangeThresholdPercent": 5, "minimumSeverityForAI": "medium" }
        })
        // Python returns the change_detection_v1 report object directly.
        return response.data;
    } catch (error) {
        console.error("Error detecting snapshot changes:", error);
        throw error;
    }
}

const detectComparisonChanges = async (oldComparison, newComparison) => {
    try {
        const response = await pythonApi.post('/v1/diff-comparisons', {
            "previousComparison": oldComparison,
            "currentComparison": newComparison,
            "settings": {
                "minimumSeverityForAI": "medium",
                "priceChangeThresholdPercent": 5,
                "rankChangeThreshold": 3,
                "ignoreLowChanges": true
            }
        })
        return response.data;
    } catch (error) {
        console.error("Error detecting comparison changes:", error);
        throw error;
    }
}

export { detectSnapshotChanges, detectComparisonChanges };