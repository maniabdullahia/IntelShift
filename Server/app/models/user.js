import mongoose from "mongoose";

const loginActivitySchema = new mongoose.Schema({
    ip: String,
    userAgent: String,
    device: String,
    location: String,
    loggedInAt: {
        type: Date,
        default: Date.now,
    },
}, { _id: false });


const userSchema = new mongoose.Schema({

    // =========================
    // BASIC INFO
    // =========================

    name: {
        type: String,
        trim: true,
        maxlength: 80,
    },

    email: {
        type: String,
        required: true,
        unique: true,
        lowercase: true,
        trim: true,
        index: true,
    },

    profilePicture: {
        type: String,
        default: "",
    },



    // =========================
    // AUTH
    // =========================

    password: {
        type: String,
        default: null,
        // required: true,
        // select: false,
        // minlength: 6,
    },

    socialSub: {
        type: String,
        default: null
    },

    refreshToken: {
        type: String,
        select: false,
        default: null,
    },

    provider: {
        type: String,
        enum: ["local", "google", "facebook"],
        default: "local",
    },



    

    // =========================
    // EMAIL VERIFICATION
    // =========================

    isEmailVerified: {
        type: Boolean,
        default: false,
    },

    emailVerificationToken: {
        type: String,
        select: false,
        default: null,
    },

    emailVerificationExpires: {
        type: Date,
        default: null,
        select: false,
    },



    // =========================
    // PASSWORD RESET
    // =========================

    passwordResetToken: {
        type: String,
        select: false,
        default: null,
    },

    passwordResetExpires: {
        type: Date,
        select: false,
        default: null,
    },



    // =========================
    // SECURITY
    // =========================

    role: {
        type: String,
        enum: ["user", "admin"],
        default: "user",
    },

    accountStatus: {
        type: String,
        enum: ["pending", "active", "suspended", "deleted", "trial", "deactivated"],
        default: "pending",
        index: true,
    },

    // Staged account-closure schedule (see account.service.js).
    deletion: {
        status: {
            type: String,
            enum: ["none", "requested", "scheduled", "deactivated"],
            default: "none",
        },
        requestedAt: { type: Date, default: null },
        confirmedAt: { type: Date, default: null },
        accessEndsAt: { type: Date, default: null, index: true }, // access cut (period end)
        deleteAt: { type: Date, default: null, index: true },     // hard delete date
        remindersSent: { type: [String], default: [] },
    },

    isSuspended: {
        type: Boolean,
        default: false,
    },

    failedLoginAttempts: {
        type: Number,
        default: 0,
    },

    lockUntil: {
        type: Date,
        default: null,
    },



    // =========================
    // Paddle / BILLING
    // =========================

    defaultPaymentMethod: {
        type: String,
        default: null,
    },



    // =========================
    // LOGIN ACTIVITY
    // =========================

    lastLoginAt: {
        type: Date,
        default: null,
    },

    lastLoginIP: {
        type: String,
        default: null,
    },

    lastUserAgent: {
        type: String,
        default: null,
    },

    loginActivity: {
        type: [loginActivitySchema],
        default: [],
        select: false,
    },



    // =========================
    // USAGE (NO BILLING HERE)
    // =========================

    usage: {
        competitorsUsed: {
            type: Number,
            default: 0,
        },

        pagesUsed: {
            type: Map,
            of: Number,
            default: {},
        },

        usageResetAt: {
            type: Date,
            default: null,
        },
    },



    // =========================
    // SETTINGS
    // =========================

    settings: {
        notifications: {
            email: { type: Boolean, default: true },
            alerts: { type: Boolean, default: true },
            reports: { type: Boolean, default: true },
        },

        // Change-alert preferences (drive the alert worker + Alert Settings UI)
        alerts: {
            frequency: { type: String, enum: ["instant", "daily"], default: "instant" },
            pricing: { type: Boolean, default: true },
            highImpact: { type: Boolean, default: true },
            homepage: { type: Boolean, default: false },
        },

        theme: {
            type: String,
            enum: ["light", "dark"],
            default: "dark",
        },
    },

}, {
    timestamps: true,
});



// =========================
// INDEXES
// =========================



// CreatedAt index
userSchema.index({ createdAt: -1 });




// =========================
// VIRTUALS
// =========================

userSchema.virtual("id").get(function () {
    return this._id.toHexString();
});

userSchema.virtual("profile").get(function () {
    return {
        id: this._id,
        name: this.name,
        email: this.email,
        profilePicture: this.profilePicture,
        role: this.role,
    };
});

userSchema.virtual("workspace", {
    ref: "Workspace",
    localField: "_id",
    foreignField: "ownerId",
    justOne: true,
});

userSchema.virtual("subscription", {
    ref: "Subscription",
    localField: "_id",
    foreignField: "userId",
    justOne: true,
    // Deterministic: if duplicate subscription records ever exist, resolve to the
    // most recent (the paid plan), never a stale trial record.
    options: { sort: { createdAt: -1 } },
});



// =========================
// METHODS
// =========================

userSchema.methods.isLocked = function () {
    return !!(this.lockUntil && this.lockUntil > Date.now());
};

userSchema.methods.getActiveSubscription = async function () {
    const Subscription = mongoose.model("Subscription");

    return await Subscription.findOne({
        userId: this._id,
        status: { $in: ["active", "trialing", "past_due"] },
    }).sort({ createdAt: -1 });
};

userSchema.methods.syncPlanFromSubscription = async function () {
    const subscription = await this.getActiveSubscription();

    if (subscription) {
        this.plan = subscription.plan;
    } else {
        this.plan = null;
    }

    await this.save();
};



// =========================
// CLEAN OUTPUT
// =========================

userSchema.methods.toJSON = function () {
    const user = this.toObject();

    delete user.password;
    delete user.refreshToken;
    delete user.emailVerificationToken;
    delete user.emailVerificationExpires;
    delete user.passwordResetToken;
    delete user.passwordResetExpires;
    delete user.__v;

    return user;
};



// =========================
// SERIALIZATION
// =========================

userSchema.set("toJSON", { virtuals: true });
userSchema.set("toObject", { virtuals: true });



const User =
    mongoose.models.User ||
    mongoose.model("User", userSchema);

export default User;

