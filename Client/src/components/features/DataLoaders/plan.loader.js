import { getPlans } from "../../../api/plan.api"

const packagesLoader = async () => {
    return getPlans();
}

export default packagesLoader;