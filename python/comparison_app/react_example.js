export async function compareWebsites({ userWebsite, competitors }) {
  const response = await fetch("http://127.0.0.1:8000/api/compare", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      userWebsite,
      competitors,
      options: {
        includeOpenAiEvidencePack: true,
        includeProductDetails: true,
        includePageContent: true,
        includeSectionDetails: true,
        includeOneToOneComparison: true,
        maxProductsPerSite: null,
        maxSectionsPerSite: null,
      },
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText);
  }

  return response.json();
}

export async function compareOneWebsite({ userWebsite, competitorWebsite }) {
  const response = await fetch("http://127.0.0.1:8000/api/compare-one", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      userWebsite,
      competitorWebsite,
      options: {
        includeOpenAiEvidencePack: true,
        includeProductDetails: true,
        includePageContent: true,
        includeSectionDetails: true,
        includeOneToOneComparison: true,
      },
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText);
  }

  return response.json();
}
