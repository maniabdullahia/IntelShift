import { useState, useEffect } from "react";

import TreeNode from "../../ui/TreeNode";
import ManualPageUrlPicker from "../../shared/ManualPageUrlPicker";
import Button from "../../ui/Button";

import Swal from "../../shared/Alert";

import { createTreeNode } from "../../../api/utils.api";
import Skeleton from "../Loadings/Skeleton";
import useAuthStore from "../../../store/auth.store";

const CompetitorPageSelection = ({ onSelection, url, onFinish, isValid}) => {

    const [treeData, setTreeData] = useState([]);
    const [loading, setLoading] = useState(false);
    const [treeSelectedPages, setTreeSelectedPages] = useState([]);
    const [manualUrls, setManualUrls] = useState([]);

    const competitorPageLimit = useAuthStore((state) => state?.user?.limits?.pageLimit);
    const selectedPageCount = treeSelectedPages.length + manualUrls.length;

    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const origin = new URL(url).origin;
                const urlWithProtocol = origin.startsWith("http") ? origin : `https://${origin}`;
                const data = await createTreeNode(urlWithProtocol);
                setTreeData(data);
            } catch (error) {
                console.error("Error fetching tree data:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [url]);

    useEffect(() => {
        onSelection([...treeSelectedPages, ...manualUrls]);
    }, [treeSelectedPages, manualUrls, onSelection]);

    if(!url) {
        Swal.fire({
            icon: 'error',
            title: 'URL Missing',
            text: 'Please provide a URL to fetch the page structure.',
        });
        return <div>Please provide a URL to fetch the page structure.</div>;
    }

    if (loading) {
        return <Skeleton lines={4} height="24px" />;
    }
    

    return (
        <div>
            <h2 className="text-2xl font-[Inter] tracking-tight mb-2">Competitor Page Selection</h2>
            <p className="text-(--text-light) mb-5">This is where you can select different competitor pages to view their details.</p>
            <p className="mb-3 inline-flex items-center rounded-full bg-(--accent)/10 px-3 py-1 text-sm font-semibold text-(--accent)">
                {selectedPageCount}/5 pages selected
            </p>
            {/* Add your selection components here */}
            <TreeNode data={treeData} homepage={url} selectionLimit={5} onSelectionChange={setTreeSelectedPages} />

            <ManualPageUrlPicker
                urls={manualUrls}
                onUrlsChange={setManualUrls}
                existingUrls={treeSelectedPages}
                selectedCount={treeSelectedPages.length}
                selectionLimit={5}
            />
            <Button title="Finish"
            onClick={onFinish}
            className="float-end mt-5"
            disabled={!isValid}
            style={{
            backgroundColor: isValid ? "var(--primary)" : "var(--border)",
            color: isValid ? "white" : "var(--text-light)",
            cursor: isValid ? "pointer" : "not-allowed",
            }} ></Button>

        </div>
    );
};

export default CompetitorPageSelection;