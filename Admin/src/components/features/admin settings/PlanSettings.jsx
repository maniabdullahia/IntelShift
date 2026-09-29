import { useEffect, useState } from "react";

import { PlusCircle, Trash2Icon } from "lucide-react";

import { getPlans } from "../../../api/plans.api";

function PlanSettings() {

    const [plans, setPlans] = useState([]);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                const plansData = await getPlans();
                setPlans(plansData);
            } catch (error) {
                console.error("Error fetching plans:", error);
            }
        };

        fetchPlans();
    }, []);


    return (
        <div className="min-h-screen bg-(--background) p-6">

            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold text-(--text)">
                    Plan Settings
                </h1>

                <p className="text-(--text-light) mt-2">
                    Manage subscription plans, features and usage limits.
                </p>
            </div>


            {/* Plans Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                {plans.length > 0 ? (

                    plans.map((plan) => (

                        <div
                            key={plan._id}
                            className="
                            bg-(--card)
                            border border-(--border)
                            rounded-lg
                            p-6
                            shadow-(--shadow-sm)
                            hover:shadow-(--shadow-md)
                            transition-all
                            duration-300
                            "
                        >

                            {/* Plan Header */}
                            <div className="flex justify-between items-start mb-5">

                                <div>
                                    <h2 className="
                                    text-xl 
                                    font-bold 
                                    text-(--text)
                                    ">
                                        {plan.displayName}
                                    </h2>

                                    <p className="
                                    text-sm 
                                    text-(--text-light)
                                    mt-1
                                    ">
                                        Subscription Plan
                                    </p>
                                </div>


                                <div className="
                                bg-(--accent)
                                text-white
                                px-3
                                py-1
                                rounded-full
                                text-sm
                                font-semibold
                                ">
                                    ${plan.price} /Month
                                </div>

                            </div>


                            {/* Description */}
                            <p className="
                            text-(--text-light)
                            text-sm
                            mb-6
                            ">
                                {plan.desc}
                            </p>



                            {/* Features */}
                            <div className="mb-6">

                                <h3 className="
                                font-semibold
                                text-(--text)
                                mb-3
                                ">
                                    Features
                                </h3>


                                <div className="flex flex-col gap-2">

                                    {plan.features?.map((feature, index) => (
                                        <div className="flex" key={index}>
                                            <span
                                                className="
                                                    bg-opacity-10
                                                    text-(--text)
                                                    px-3
                                                    py-1
                                                    rounded-full
                                                    text-xs
                                                    "
                                                >
                                                {feature}
                                            </span>
                                            <button title="Click to delete feature" className="ml-2 cursor-pointer text-(--danger) hover:text-(--danger-dark)">
                                                <Trash2Icon size={16} />
                                            </button>
                                        </div>
                                    ))}

                                    {/* Add Feature option */}

                                    <div className="flex">
                                        <input placeholder="Add a new feature..." className="px-3 text-(--text) text-xs " />
                                        <button title="Click to add feature" className="ml-2 cursor-pointer text-(--primary) hover:text-(--secondary)">
                                            <PlusCircle size={16} />
                                        </button>
                                    </div>
                                </div>

                            </div>



                            {/* Limits */}
                            <div>

                                <h3 className="
                                font-semibold
                                text-(--text)
                                mb-3
                                ">
                                    Limits
                                </h3>


                                <div className="
                                space-y-3
                                text-sm
                                ">


                                    <div className="
                                    flex
                                    justify-between
                                    bg-(--background)
                                    px-3
                                    rounded-sm
                                    ">
                                        <span className="text-(--text-light)">
                                            Competitors
                                        </span>

                                        <span className="
                                        font-semibold
                                        text-(--text)
                                        ">
                                            {plan.limits?.competitors ?? "-"}
                                        </span>
                                    </div>



                                    <div className="
                                    flex
                                    justify-between
                                    bg-(--background)
                                    px-3
                                    rounded-sm
                                    ">
                                        <span className="text-(--text-light)">
                                            Pages per Competitor
                                        </span>

                                        <span className="
                                        font-semibold
                                        text-(--text)
                                        ">
                                            {plan.limits?.pagesPerCompetitor ?? "-"}
                                        </span>
                                    </div>


                                </div>

                            </div>


                        </div>

                    ))

                ) : (

                    <div className="
                    col-span-full
                    text-center
                    text-(--text-light)
                    py-10
                    ">
                        No plans found.
                    </div>

                )}

            </div>

        </div>
    )
}

export default PlanSettings;