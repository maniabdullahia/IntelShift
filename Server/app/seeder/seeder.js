import seedPlans from "./plan.seeder.js";
import seedAdmin from "./admin.seeder.js";

const seedAll = async () => {
    await seedPlans();
    await seedAdmin();
};

export default seedAll;