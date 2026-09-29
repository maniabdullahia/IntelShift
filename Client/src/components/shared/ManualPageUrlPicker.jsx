import { useState } from "react";

import Swal from "./Alert";
import { validatePageUrl } from "../../api/utils.api";

function ManualPageUrlPicker({
  urls = [],
  onUrlsChange,
  existingUrls = [],
  selectedCount = 0,
  selectionLimit = Infinity,
  title = "Add a page manually",
  description = "Didn’t find a page in the tree? Paste the full URL and add it here.",
  placeholder = "https://example.com/about",
}) {
  const [manualUrlInput, setManualUrlInput] = useState("");
  const [isChecking, setIsChecking] = useState(false);

  const addHttpsPrefix = (url) => {
    if (!url.startsWith('https://')) {
      return `https://${url}`;
    }
    return url;
  };


  const normalizeUrl = (value = "") => value.trim().replace(/\/+$/, "");

  const toAbsoluteUrl = (value = "") => {
    const trimmedValue = normalizeUrl(value);

    if (!trimmedValue) {
      return "";
    }

    const urlWithProtocol = /^https?:\/\//i.test(trimmedValue)
      ? trimmedValue
      : `https://${trimmedValue}`;

    try {
      return normalizeUrl(new URL(urlWithProtocol).toString());
    } catch {
      return "";
    }
  };

  const handleAddManualUrl = async () => {
    const cleanedUrl = toAbsoluteUrl(manualUrlInput);

    if (!cleanedUrl) {
      Swal.fire({
        icon: "error",
        title: "Invalid URL",
        text: "Please enter a valid page URL before adding it.",
      });
      return;
    }

    setIsChecking(true);

    try {
      await validatePageUrl(cleanedUrl);
    } catch (error) {
      const status = error?.response?.status;
      const message =
        error?.response?.data?.message ||
        error?.message ||
        "Unable to verify the website.";

      Swal.fire({
        icon: "error",
        title: status === 404 ? "Page Not Found" : "Unable to Verify URL",
        text: message,
      });

      return;
    } finally {
      setIsChecking(false);
    }

    const alreadySelected = [...existingUrls, ...urls].some(
      (page) => normalizeUrl(page) === cleanedUrl,
    );

    if (alreadySelected) {
      setManualUrlInput("");
      return;
    }

    if (selectedCount + urls.length >= selectionLimit) {
      Swal.fire({
        icon: "warning",
        title: "Limit Exceeded!",
        text: "You have exceeded the maximum number of pages you can select.",
        confirmButtonColor: "var(--accent)",
      });
      return;
    }

    onUrlsChange([...urls, cleanedUrl]);
    setManualUrlInput("");
  };

  const handleRemoveManualUrl = (urlToRemove) => {
    onUrlsChange(urls.filter((url) => url !== urlToRemove));
  };

  const handleManualUrlKeyDown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      handleAddManualUrl();
    }
  };

  const hasUrls = urls.length > 0;

  return (
    <div
      style={{
        marginTop: "1.5rem",
        padding: "1rem",
        borderRadius: "16px",
        border: "1px solid var(--border)",
        background: "var(--card)",
      }}
    >
      <h3
        style={{
          fontSize: "18px",
          fontWeight: "700",
          marginBottom: "0.5rem",
          color: "var(--primary)",
          fontFamily: "var(--font-heading)",
        }}
      >
        {title}
      </h3>
      <p
        style={{
          fontSize: "14px",
          color: "var(--text-light)",
          marginBottom: "0.75rem",
          lineHeight: "1.5",
        }}
      >
        {description}
      </p>

      <div className="flex flex-row items-stretch gap-2">
        <input
          value={manualUrlInput}
          onChange={(event) => setManualUrlInput(event.target.value)}
          onBlur={(e) => setManualUrlInput(addHttpsPrefix(e.target.value))}
          onKeyDown={handleManualUrlKeyDown}
          type="url"
          placeholder={placeholder}
          aria-label="Manual page URL"
          disabled={isChecking}
          className="min-w-0 flex-1 rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-(--accent) focus:ring-2 focus:ring-(--accent)/20"
        />

        <button
          type="button"
          onClick={handleAddManualUrl}
          disabled={isChecking}
          className="inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-xl bg-(--primary) px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90"
        >
          {isChecking ? "Checking…" : "Add URL"}
        </button>
      </div>

      {hasUrls && (
        <div className="mt-4 space-y-2">
          <span className="text-sm font-semibold text-(--text-light)">
            Manually added URLs
          </span>
          <div className="flex flex-wrap gap-2">
            {urls.map((manualUrl) => (
              <span
                key={manualUrl}
                className="inline-flex max-w-full items-center rounded-full bg-(--accent)/10 px-3 py-1 text-xs font-medium text-(--accent)"
              >
                <span className="truncate">{manualUrl}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveManualUrl(manualUrl)}
                  className="ml-2 text-(--accent) opacity-70 transition hover:opacity-100"
                  aria-label={`Remove ${manualUrl}`}
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default ManualPageUrlPicker;