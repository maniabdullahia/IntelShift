import { useState } from 'react';

import ProcessStepper from "../../ui/ProcessStepper";
import CompetitorProfile from "./CompetitorProfile";
// The SAME mapped "Choose what to track" experience as the onboarding selection
// modal — the competitor's collections auto-paired to yours.
import CompetitorMappingPanel from "./CompetitorMappingPanel";

import Swal from '../../shared/Alert';

import useWorkspaceStore from '../../../store/workspace.store';
import useAuthStore from '../../../store/auth.store';

const CreateCompetitor = ({ onCancel }) => {

    const [competitorName, setCompetitorName] = useState("");
    const [competitorUrl, setCompetitorUrl] = useState("");
    const [selectedPages, setSelectedPages] = useState([]);
    const [pagePairs, setPagePairs] = useState([]);
    const [currentStep, setCurrentStep] = useState(1);


    const addCompetitor = useWorkspaceStore((state) => state.addCompetitor);
    const workspace = useWorkspaceStore((state) => state.workspace);
    const workspaceId = useWorkspaceStore((state) => state.workspaceId || state.workspace?._id);
    const pagesPerCompetitor = useAuthStore((state) => state?.user?.subscription?.planId?.limits?.pagesPerCompetitor) || 5;

    const ownerSite = workspace?.competitors?.find((c) => c.role === "Owner");
    // For auto-suggesting competitors: the user's own store URL, industry, and the
    // domains already added (so we don't re-suggest them).
    const ownerUrl = workspace?.url || ownerSite?.websiteUrl || ownerSite?.storeUrl || (ownerSite?.domain ? `https://${ownerSite.domain}` : "");
    const excludeDomains = (workspace?.competitors || []).map((c) => c.domain).filter(Boolean);

    const cleanName = (value) => value.trim().replace(/\s+/g, " ");
    const cleanURL = (value) => value.trim().replace(/\s+/g, "");

    const normalizeUrl = (value = "") => value.replace(/\/+$/, "");

    
  const ensureHomepageIncluded = (pages = [], homepageUrl = "") => {
        const normalizedHomepage = normalizeUrl(homepageUrl);

        if (!normalizedHomepage) {
        return pages;
        }

        const hasHomepage = pages.some(
        (page) => normalizeUrl(page || "") === normalizedHomepage,
        );

        if (hasHomepage) {
        return pages;
        }

        return [normalizedHomepage, ...pages.filter(Boolean)];
    };

    const isStepValid = (stepId) =>  {
        const sanitizedCompetitorName = cleanName(competitorName);
        const sanitizedURL = cleanURL(competitorUrl);

        if(stepId === 1){
            return Boolean(sanitizedCompetitorName && sanitizedURL)
        }

        if(stepId === 2){
            const pages = selectedPages.length;
            return pages > 0;
        }
    };

    const getBlockedMessage = (stepId) => {
    if (stepId === 1) return "Competitor name and Competitor URL are required.";
    if (stepId === 2) return "Select at least one competitor page to continue.";
    return "Please complete required fields to continue.";
  };

  const canJumpTo = (targetStep) => {
    // allow jumping back always
    if (targetStep <= 1) return true;

    for (let i = 1; i < targetStep; i++) {
      if (!isStepValid(i)) return false;
    }

    return true;
  };

    

    const handleFinish = () => {
        const sanitizedCompetitorName = cleanName(competitorName);
        const sanitizedURL = cleanURL(competitorUrl);

        const competitorPagesToSubmit = ensureHomepageIncluded(
            selectedPages,
            sanitizedURL,
        )

        if(!competitorUrl || selectedPages.length === 0) {
            Swal.fire({
                icon: 'error',
                title: 'Invalid Input',
                text: 'Please fill in all required fields and select at least one page to monitor.',
            });
            return;
        }        

        const competitorData = {
            name: sanitizedCompetitorName,
            url: competitorUrl,
            selectedPages: competitorPagesToSubmit,
            // Persist the 1:1 mapping (which of your pages each competitor page
            // pairs with), exactly like onboarding.
            pagePairs: pagePairs
                .filter((p) => p.competitorUrl && p.status === "matched")
                .map((p) => ({ workspaceUrl: p.workspaceUrl, competitorUrl: p.competitorUrl, status: p.status })),
            role: "Competitor",
            workspaceId: workspaceId
        };
        addCompetitor(competitorData);
        onCancel();
    };

    const steps = [
        {
            id: 1,
            label: "Competitor Details",
            description: "Provide basic information about your competitor.",
            component: <CompetitorProfile
                competitorName={competitorName}
                setCompetitorName={setCompetitorName}
                competitorUrl={competitorUrl}
                setCompetitorUrl={setCompetitorUrl}
                ownerUrl={ownerUrl}
                industry={workspace?.industry}
                excludeDomains={excludeDomains}
            />
        },
        {
            id: 2,
            label: "Page Selection",
            description: "Select the competitor pages you want to monitor.",
            component: <CompetitorMappingPanel
                url={competitorUrl}
                competitorName={cleanName(competitorName)}
                ownerName={workspace?.name || "your store"}
                pageLimit={pagesPerCompetitor}
                onPageSelection={setSelectedPages}
                onMappingChange={setPagePairs}
                isActive={currentStep === 2}
            />
        }
    ];

    return (
        <div className="p-10">
            <div className="flex">
                <h1 className="text-4xl font-bold font-[Inter] tracking-tight mb-6">Create Competitor</h1>
                <button
                    className="ml-auto text-sm text-gray-500 hover:text-gray-700"
                    onClick={onCancel}
                >
                    Back to Competitors
                </button>
            </div>
            <p className="text-(--text-light) mb-4">Follow the steps to add a new competitor to your monitoring list.</p>
            <ProcessStepper
            currentStep={currentStep}
            steps={steps}
            onStepChange={setCurrentStep}
            canProceed={isStepValid(currentStep)}
            nextBlockedMessage={getBlockedMessage(currentStep)}
            canJumpTo={canJumpTo}
            finalActions={
                <button
                    type="button"
                    onClick={handleFinish}
                    disabled={!isStepValid(2)}
                    style={{
                        padding: "13px 24px",
                        background: isStepValid(2) ? "var(--accent)" : "var(--border)",
                        color: isStepValid(2) ? "#fff" : "var(--text-light)",
                        border: "none",
                        borderRadius: "12px",
                        fontWeight: 700,
                        boxShadow: isStepValid(2) ? "0 8px 24px rgba(255,107,107,0.3)" : "none",
                        cursor: isStepValid(2) ? "pointer" : "not-allowed",
                        fontFamily: "var(--font-sans)",
                        fontSize: "14px",
                    }}
                >
                    Add competitor
                </button>
            } />
        </div>
    );
}

export default CreateCompetitor;