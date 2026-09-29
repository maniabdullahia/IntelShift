import Admin from "../models/admin.js";

const seedAdmin = async () => {

    const existingAdmin = await Admin.find({})

    if (existingAdmin.length > 0) {
        console.log("Admin already seeded, skipping...");
        return;
    }
    const admin = await Admin.create({
        email: "admin@intelshift.ai",
        password: "admin"
    });
}

export default seedAdmin;