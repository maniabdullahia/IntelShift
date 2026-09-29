import { useState, useEffect } from 'react';
// import useWorkspaceStore from '../../../store/workspace.store'
// import useAuthStore from '../../../store/auth.store';

import { useParams } from 'react-router';

import { getAnalysis } from '../../../api/workspace.api';

// import { 
//   AnalysisIdentity,
//   CollectionData, 
//   FeatureMatrix, 
//   KeyInsights, 
//   PortfolioMatrix, 
//   Positioning, 
//   PriceAnalysis, 
//   QuantitativeSignals, 
//   Recommendation, 
//   SeoAnalysis, 
//   Summary, 
//   SwotAnalysis, 
//   TopProducts, 
//   TrustSignals,
//   ProductComparison,
//   VisualAnalysis
// } from '../../../components/features/AnalysisSections';

import { AnalysisPage } from '../../../components/features/AnalysisSections';

function Analysis() {

  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(true);
  // const [props, setProps] = useState({});
  const { analysisId } = useParams();

  // const analysisData = useWindowController((state) => state.currentScreenData);
  // const subscriptionType = useAuthStore((state) => state.user.subscriptionType);

  useEffect(() => {
    if (analysisId) {
      const fetchAnalysis = async () => {
        try {
          setLoading(true);
          const response = await getAnalysis(analysisId);
          console.log("Fetched analysis data:", response);
          setAnalysis(response.analysis);
          
        } catch (error) {
          console.error("Error fetching analysis:", error);
        } finally {
          setLoading(false);
        }
      }

      fetchAnalysis();
    }
  }, [analysisId]);



  // const analysisData = useWorkspaceStore((state) => state.workspace.analysis[0].result);
  // const analysiIdentity = analysisData?.analysis_identity;
  // const executiveSummary = analysisData?.executive_summary;
  // const collectionData = analysisData?.collection_data;
  // const featureMatrix = analysisData?.feature_matrix;
  // const keyInsights = analysisData?.key_insights;
  // const portfolioMatrix = analysisData?.portfolio_matrix
  // const positioning = analysisData?.positioning
  // const priceAnalysis = analysisData?.price_analysis
  // const quantitativeSignals = analysisData?.quantitative_signals
  // const topProducts = analysisData?.top_products
  // const trustSignals = analysisData?.trust_signals
  // const recommendations = analysisData?.recommendations
  // const seoAnalysis = analysisData?.seo_analysis
  // const swotAnalysis = analysisData?.swot_analysis;

  if (loading) {
    return (
      <div className='flex items-center justify-center h-full'>
        <div className='text-center'>
          <div className='text-2xl font-semibold text-gray-700'>Loading Analysis...</div>
          <div className='text-gray-500'>Please wait while we fetch the analysis data.</div>
        </div>
      </div>
    )
  }

  const props = {
    aiAnalysis: analysis?.data?.result,
    comparison: analysis?.data?.comparison,
    aiPayload: analysis?.data?.payload,
    competitorId: analysis?.competitors?.competitorId,
  }

  console.log('Analysis props:', props);

  return (
    <div className='max-w-5xl mx-auto space-y-8 p-6'>
      {/* <AnalysisIdentity {...props} />
      <Summary {...props} />
      <CollectionData {...props} />
      <FeatureMatrix {...props} />
      <KeyInsights {...props} />
      <PortfolioMatrix {...props} />
      <Positioning {...props} />
      <PriceAnalysis {...props} />
      <QuantitativeSignals {...props} />
      <TopProducts {...props} />
      <ProductComparison {...props} />
      <VisualAnalysis {...props} />
      <TrustSignals {...props} />
      <Recommendation {...props} />
      <SeoAnalysis {...props} />
      <SwotAnalysis {...props} /> */}

      <AnalysisPage {...props} />
    </div>
  )
}

export default Analysis
