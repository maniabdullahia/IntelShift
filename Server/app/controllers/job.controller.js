import Job from "../models/job.js";
import JobEvent from "../models/jobEvent.js";

/*
|--------------------------------------------------------------------------
| GET ALL JOBS (Dashboard)
|--------------------------------------------------------------------------
*/

export const getJobs = async (req, res) => {
  try {
    const {
      status,
      queueName,
      userId,
      workspaceId,
      page = 1,
      limit = 20,
    } = req.query;

    const filter = {};

    if (status) filter.status = status;
    if (queueName) filter.queueName = queueName;
    if (userId) filter.userId = userId;
    if (workspaceId) filter.workspaceId = workspaceId;

    const skip = (page - 1) * limit;

    const jobs = await Job.find(filter)
      .sort({ createdAt: -1 })
      .populate("userId", "name email")
      .populate("workspaceId", "name")
      .populate("competitorId", "name")
      .populate("pageId", "url")
      .skip(skip)
      .limit(Number(limit));

    const total = await Job.countDocuments(filter);

    res.json({
      success: true,
      data: jobs,
      pagination: {
        total,
        page: Number(page),
        pages: Math.ceil(total / limit),
      },
    });

  } catch (err) {
    res.status(500).json({
      success: false,
      message: err.message,
    });
  }
};

/*
|--------------------------------------------------------------------------
| GET SINGLE JOB
|--------------------------------------------------------------------------
*/

export const getJobById = async (req, res) => {
  try {
    const { jobId } = req.params;

    const job = await Job.findOne({ jobId });

    if (!job) {
      return res.status(404).json({
        success: false,
        message: "Job not found",
      });
    }

    res.json({
      success: true,
      data: job,
    });

  } catch (err) {
    res.status(500).json({
      success: false,
      message: err.message,
    });
  }
};

/*
|--------------------------------------------------------------------------
| GET JOB EVENTS (TIMELINE)
|--------------------------------------------------------------------------
*/

export const getJobEvents = async (req, res) => {
  try {
    const { jobId } = req.params;

    const events = await JobEvent.find({ jobId })
      .sort({ createdAt: 1 });

    res.json({
      success: true,
      data: events,
    });

  } catch (err) {
    res.status(500).json({
      success: false,
      message: err.message,
    });
  }
};