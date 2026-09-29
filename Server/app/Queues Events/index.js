import "./analysis.event.js";
import "./competitor.event.js";
import "./workspace.event.js";
// NOTE: recon persistence + stage-advance now live in the recon WORKER
// (app/workers/recon.worker.js), so recon.event.js is intentionally NOT
// registered — running it would overwrite the worker's saved recon with an
// empty return value.
