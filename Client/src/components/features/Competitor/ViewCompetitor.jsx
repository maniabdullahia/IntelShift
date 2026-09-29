import {
	AlertTriangle,
	ArrowLeft,
	CheckCircle2,
	Clock3,
	ExternalLink,
	Globe,
	LoaderCircle,
	RefreshCw,
	ShieldUser,
	Trash2,
	User,
	TrendingUp,
	BarChart3,
	Package,
	DollarSign,
	Filter,
	Activity,
	Sparkles,
} from "lucide-react";
import { useState, useMemo } from "react";
import Alert from "../../shared/Alert";
import useWorkspaceStore from "../../../store/workspace.store";
import useAuthStore from "../../../store/auth.store";
import TrackedPagesManager from "../Pages/TrackedPagesManager";

import { useNavigate, useParams } from "react-router-dom";

const defaultData = {
	name: "Unknown Competitor",
	role: "Competitor",
	websiteUrl: "",
	domain: "-",
	scanStatus: "Pending",
	lastRebuiltAt: null,
	updatedAt: null,
	pages: [],
};

const toLabel = (value = "") => {
	if (!value) return "Unknown";
	return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase();
};

const formatDateTime = (value) => {
	if (!value) return "Not available";

	const date = new Date(value);
	if (Number.isNaN(date.getTime())) return "Invalid date";

	return date.toLocaleString();
};

const statusPillClass = (status) => {
	const normalized = String(status || "").toLowerCase();

	if (normalized === "completed") {
		return "border-[rgba(38,222,129,0.4)] bg-[rgba(38,222,129,0.12)] text-(--success)";
	}

	if (normalized === "failed") {
		return "border-[rgba(252,92,101,0.4)] bg-[rgba(252,92,101,0.12)] text-(--danger)";
	}

	if (normalized === "processing" || normalized === "analyzing") {
		return "border-[rgba(254,211,48,0.5)] bg-[rgba(254,211,48,0.15)] text-[rgba(125,99,0,1)]";
	}

	return "border-[rgba(99,110,114,0.35)] bg-[rgba(99,110,114,0.1)] text-(--text-light)";
};

const getStatusIcon = (status) => {
	const normalized = String(status || "").toLowerCase();

	if (normalized === "completed") {
		return <CheckCircle2 size={14} aria-hidden="true" />;
	}

	if (normalized === "failed") {
		return <AlertTriangle size={14} aria-hidden="true" />;
	}

	if (normalized === "processing" || normalized === "analyzing") {
		return <LoaderCircle size={14} className="animate-spin" aria-hidden="true" />;
	}

	return <Clock3 size={14} aria-hidden="true" />;
};

function ViewCompetitor() {
	const [isDeleting, setIsDeleting] = useState(false);
	const navigate = useNavigate();
	const { competitorId } = useParams();
	const workspaceId = useWorkspaceStore((state) => state?.workspace?._id || state?.workspace?.id);
	const deleteCompetitor = useWorkspaceStore((state) => state.deleteCompetitor);
	const workspace = useWorkspaceStore((state) => state.workspace);

	// Managing competitors is a paid capability — the free trial is view-only.
	const planName = useAuthStore((state) => state.user?.subscription?.planId?.name);
	const canManage = planName && String(planName).toLowerCase() !== "trial";

	// Resolve competitor from the workspace store using the route param.
	const competitor = useMemo(() => {
		const storeCompetitor = workspace?.competitors?.find(
			(c) => String(c._id) === String(competitorId)
		);

		if (storeCompetitor) {
			return {
				...defaultData,
				...storeCompetitor,
				pages: Array.isArray(storeCompetitor.pages) ? storeCompetitor.pages : [],
			};
		}

		return {
			...defaultData,
			name: competitorId ? "Competitor not found" : defaultData.name,
			pages: [],
		};
	}, [workspace, competitorId]);

	// The homepage is auto-tracked and shouldn't be counted among tracked/analyzed
	// pages. (Site root "/" — treat unparseable urls as non-homepage.)
	const isHome = (url) => {
		const s = String(url || "");
		try {
			const u = new URL(/^https?:\/\//i.test(s) ? s : `https://${s}`);
			return u.pathname === "" || u.pathname === "/";
		} catch {
			return false;
		}
	};

	const pageStats = competitor.pages.reduce(
		(acc, page) => {
			if (isHome(page?.url)) return acc; // homepage isn't a tracked page
			const normalized = String(page?.scanStatus || "").toLowerCase();

			if (normalized === "completed") acc.completed += 1;
			else if (normalized === "failed") acc.failed += 1;
			else acc.pending += 1;

			return acc;
		},
		{ completed: 0, failed: 0, pending: 0 }
	);

	// "Pages Tracked" excludes the auto-tracked homepage and pages staged to add
	// (not monitored until the next run); staged removals still count until applied.
	const trackedCount = (competitor.pages || []).filter(
		(p) => p?.pendingChange !== "add" && !isHome(p?.url)
	).length;

	const quickStats = [
		{
			id: "role",
			label: "Role",
			value: competitor.role || "-",
			icon: <ShieldUser size={16} aria-hidden="true" />,
		},
		{
			id: "domain",
			label: "Domain",
			value: competitor.domain || "-",
			icon: <Globe size={16} aria-hidden="true" />,
		},
		{
			id: "pages",
			label: "Pages Tracked",
			value: String(trackedCount),
			icon: <User size={16} aria-hidden="true" />,
		},
	];

	const handleGoBack = () => {
		navigate("/competitors");
	};

	const handleDelete = async () => {
		const competitorId = competitor?._id || competitor?.id;

		if (!competitorId) {
			Alert.fire({
				icon: "error",
				title: "Error",
				text: "Competitor identifier is missing. Unable to delete competitor.",
			});
			return;
		}

		const result = await Alert.fire({
			title: "Stop tracking this competitor?",
			text: "It's fully removed at your next monitoring run — reversible until then. Its pages, analysis and history are deleted then.",
			icon: "warning",
			iconColor: "#fc5c65",
			showCancelButton: true,
			confirmButtonColor: "#fc5c65",
			cancelButtonColor: "#1a1a2e",
			confirmButtonText: "Remove at next run",
			cancelButtonText: "Keep",
		});

		if (result.isConfirmed) {
			setIsDeleting(true);
			try {
				await deleteCompetitor(competitorId, workspaceId);
				navigate("/competitors");
			} catch (error) {
				setIsDeleting(false);
				Alert.fire({
					icon: "error",
					title: "Delete Failed",
					text: error?.message || "Failed to delete competitor. Please try again.",
				});
			}
		}
	};

	return (
		<section className="min-h-screen bg-linear-to-br from-[#f8f9fa] to-white p-4 sm:p-8">
			<div className="mx-auto max-w-6xl">
				{/* Header Section */}
				<div className="mb-8 flex items-start justify-between gap-4">
					<div className="flex items-start gap-4 flex-1">
						<button
							type="button"
							onClick={handleGoBack}
							className="mt-1 inline-flex items-center justify-center rounded-lg bg-white border border-gray-200 p-2 text-gray-700 hover:bg-gray-50 transition-all duration-200 shrink-0"
							aria-label="Go back"
						>
							<ArrowLeft size={20} />
						</button>
						<div className="flex-1 min-w-0">
							<p className="text-xs font-semibold uppercase tracking-wider text-gray-500">Competitor Overview</p>
							<h1 className="mt-2 font-(--font-heading) text-4xl text-(--primary) truncate">{competitor.name}</h1>
							<a
								href={competitor.websiteUrl || "#"}
								target="_blank"
								rel="noreferrer"
								className="mt-3 inline-flex items-center gap-2 text-sm font-medium text-(--secondary) hover:text-(--accent) transition-colors"
							>
								<Globe size={16} />
								<span className="truncate">{competitor.websiteUrl || "Website not available"}</span>
								<ExternalLink size={14} className="shrink-0" />
							</a>
						</div>
					</div>

					<span
						className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-xs font-semibold uppercase tracking-wider shrink-0 ${statusPillClass(
							competitor.scanStatus
						)}`}
					>
						{getStatusIcon(competitor.scanStatus)}
						{toLabel(competitor.scanStatus)}
					</span>
				</div>

				{/* Stats Grid */}
				<div className="grid gap-4 mb-8 sm:grid-cols-2 lg:grid-cols-4">
					{quickStats.map((stat) => (
						<article
							key={stat.id}
							className="rounded-xl border border-gray-200 bg-white p-5 hover:shadow-md transition-all duration-200"
						>
							<div className="flex items-start justify-between">
								<div>
									<p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">{stat.label}</p>
									<p className="text-2xl font-bold text-(--primary)">{stat.value}</p>
								</div>
								<div className="text-(--secondary) opacity-80">{stat.icon}</div>
							</div>
						</article>
					))}
				</div>

				{/* Timeline Info */}
				<div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
					<h3 className="text-lg font-bold text-(--primary) mb-6 flex items-center gap-2">
						<Activity size={20} className="text-(--secondary)" />
						Timeline
					</h3>
					<div className="grid sm:grid-cols-2 gap-6">
						<div className="flex items-start gap-4">
							<div className="flex flex-col items-center shrink-0">
								<div className="w-4 h-4 rounded-full bg-(--secondary)" />
								<div className="w-1 h-12 bg-linear-to-b from-(--secondary) to-transparent" />
							</div>
							<div className="flex-1 pt-1">
								<p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">Last Rebuild</p>
								<p className="text-sm font-medium text-(--text)">{formatDateTime(competitor.lastRebuiltAt)}</p>
							</div>
						</div>
						<div className="flex items-start gap-4">
							<div className="flex flex-col items-center shrink-0">
								<div className="w-4 h-4 rounded-full bg-(--accent)" />
							</div>
							<div className="flex-1 pt-1">
								<p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">Last Updated</p>
								<p className="text-sm font-medium text-(--text)">{formatDateTime(competitor.updatedAt)}</p>
							</div>
						</div>
					</div>
				</div>

				{/* Pages Analysis */}
				<div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
					<div className="flex items-center justify-between mb-6">
						<h3 className="text-lg font-bold text-(--primary) flex items-center gap-2">
							<BarChart3 size={20} className="text-(--secondary)" />
							Pages Analysis
						</h3>
						<span className="inline-flex items-center gap-2 rounded-full bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-700">
							Total: {pageStats.completed + pageStats.pending + pageStats.failed}
						</span>
					</div>

					<div className="grid grid-cols-3 gap-3 mb-6">
						<div className="rounded-lg bg-linear-to-br from-green-50 to-emerald-50 border border-green-200 p-4">
							<p className="text-xs font-medium text-green-700 uppercase tracking-wide">Completed</p>
							<p className="text-3xl font-bold text-green-700 mt-2">{pageStats.completed}</p>
						</div>
						<div className="rounded-lg bg-linear-to-br from-amber-50 to-yellow-50 border border-amber-200 p-4">
							<p className="text-xs font-medium text-amber-700 uppercase tracking-wide">Pending</p>
							<p className="text-3xl font-bold text-amber-700 mt-2">{pageStats.pending}</p>
						</div>
						<div className="rounded-lg bg-linear-to-br from-red-50 to-rose-50 border border-red-200 p-4">
							<p className="text-xs font-medium text-red-700 uppercase tracking-wide">Failed</p>
							<p className="text-3xl font-bold text-red-700 mt-2">{pageStats.failed}</p>
						</div>
					</div>

					{competitor._id ? (
						<TrackedPagesManager competitorId={competitor._id} role={competitor.role} />
					) : (
						<div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-8 text-center">
							<p className="text-gray-500 text-sm font-medium">No pages found for this competitor yet.</p>
						</div>
					)}
				</div>

				{/* Product Collections Analysis */}
				{/* {competitor.analysisData?.data && Object.keys(competitor.analysisData.data).length > 0 && (
					<div className="rounded-2xl border border-gray-200 bg-white p-6 mb-8 shadow-sm">
						<h3 className="text-lg font-bold text-(--primary) mb-6 flex items-center gap-2">
							<Package size={20} className="text-(--secondary)" />
							Product Collections Analysis
						</h3>
						<div className="space-y-4">
							{Object.entries(competitor.analysisData.data).map(([pageId, pageData], idx) => (
								<div
									key={pageId}
									className="rounded-xl border border-gray-200 bg-gradient-to-br from-gray-50 to-white p-5 hover:border-gray-300 transition-all"
								>
									<div className="flex items-start justify-between gap-4 mb-4">
										<div className="flex-1 min-w-0">
											<h4 className="text-base font-bold text-(--primary)">{pageData.page?.collectionName}</h4>
											<p className="text-xs text-gray-500 mt-1 truncate">{pageData.page?.url}</p>
										</div>
										<div className="text-right flex-shrink-0">
											<p className="text-2xl font-bold text-(--secondary)">{pageData.productStats?.productCount}</p>
											<p className="text-xs text-gray-500">products</p>
										</div>
									</div>

									<div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
										<div className="rounded-lg bg-white border border-gray-200 p-3">
											<p className="text-xs font-medium text-gray-600">Currency</p>
											<p className="text-sm font-bold text-gray-900 mt-1">{pageData.productStats?.currency}</p>
										</div>
										<div className="rounded-lg bg-white border border-gray-200 p-3">
											<p className="text-xs font-medium text-gray-600">Min Price</p>
											<p className="text-sm font-bold text-(--secondary) mt-1">{pageData.productStats?.priceRange?.min}</p>
										</div>
										<div className="rounded-lg bg-white border border-gray-200 p-3">
											<p className="text-xs font-medium text-gray-600">Max Price</p>
											<p className="text-sm font-bold text-(--secondary) mt-1">{pageData.productStats?.priceRange?.max}</p>
										</div>
										<div className="rounded-lg bg-white border border-gray-200 p-3">
											<p className="text-xs font-medium text-gray-600">Out of Stock</p>
											<p className="text-sm font-bold text-amber-600 mt-1">{pageData.productStats?.outOfStockCount || 0}</p>
										</div>
									</div>

									<div className="flex flex-wrap gap-2">
										{pageData.productStats?.hasFilters && (
											<span className="inline-flex items-center gap-1.5 rounded-full bg-blue-100 px-3 py-1 text-xs font-semibold text-blue-700">
												<Filter size={14} />
												Filters Available
											</span>
										)}
										{pageData.productStats?.hasSort && (
											<span className="inline-flex items-center gap-1.5 rounded-full bg-purple-100 px-3 py-1 text-xs font-semibold text-purple-700">
												<TrendingUp size={14} />
												Sort Available
											</span>
										)}
									</div>
								</div>
							))}
						</div>
					</div>
				)} */}

				{/* Delete Section — paid plans only (free trial is view-only) */}
				{canManage ? (
					<div className="rounded-2xl border-2 border-red-300 bg-linear-to-br from-red-50 via-red-50 to-rose-50 p-8 shadow-lg">
						<div className="grid sm:grid-cols-3 gap-8 items-center">
							<div className="sm:col-span-2">
								<div className="flex items-start gap-4">
									<div className="inline-flex items-center justify-center w-14 h-14 rounded-full bg-red-200 shrink-0">
										<Trash2 size={28} className="text-red-700" />
									</div>
									<div className="flex-1">
										<h3 className="text-xl font-bold text-red-900">Delete Competitor</h3>
										<p className="text-sm text-red-700 mt-2 leading-relaxed">
											This action cannot be undone. All tracked pages, analysis data, and historical records will be permanently removed from your workspace.
										</p>
									</div>
								</div>
							</div>

							<div className="flex flex-col gap-3">
								<button
									type="button"
									onClick={handleDelete}
									disabled={isDeleting}
									className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-red-600 px-6 py-3 text-sm font-semibold text-white hover:bg-red-700 transition-all duration-200 disabled:opacity-60 disabled:cursor-not-allowed shadow-md hover:shadow-lg"
								>
									<Trash2 size={18} />
									{isDeleting ? "Deleting..." : "Delete Competitor"}
								</button>
								<button
									type="button"
									onClick={handleGoBack}
									className="w-full px-6 py-3 rounded-lg border border-red-300 bg-white text-red-700 font-semibold hover:bg-red-50 transition-all duration-200"
								>
									Cancel
								</button>
							</div>
						</div>
					</div>
				) : (
					<div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-[rgba(78,205,196,0.35)] bg-[rgba(78,205,196,0.08)] p-6">
						<p className="text-sm text-(--text)">
							Managing competitors — including removing them — is available on paid plans.
						</p>
						<button
							type="button"
							onClick={() => navigate("/settings/billing")}
							className="inline-flex items-center gap-1.5 rounded-lg bg-(--accent) px-4 py-2 text-sm font-bold text-white transition hover:bg-(--accent-dark)"
						>
							<Sparkles size={14} /> Upgrade
						</button>
					</div>
				)}
			</div>
		</section>
	);
}

export default ViewCompetitor;
