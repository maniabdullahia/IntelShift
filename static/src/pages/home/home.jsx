import './home.css';

import SEO from '../../components/seo/SEO';
import Hero from '../../components/sections/Hero';
import LongMarquee from '../../components/sections/LongMarquee';
import Problem from '../../components/sections/Problem';
import HowItWorks from '../../components/sections/HowItWorks';
import ProductIntelligence from '../../components/sections/ProductIntelligence';
import FeaturesGrid from '../../components/sections/FeaturesGrid';
import UseCases from '../../components/sections/UseCases';
import Demo from '../../components/sections/Demo';
import Trust from '../../components/sections/Trust';
import Pricing from '../../components/sections/Pricing';
import Faq from '../../components/sections/Faq';
import FinalCTA from '../../components/sections/FinalCTA';

const homeStructuredData = {
  '@context': 'https://schema.org',
  '@type': 'WebPage',
  '@id': 'https://intelshift.ai/#webpage',
  'url': 'https://intelshift.ai/',
  'name': 'IntelShift — AI-Powered Competitor Intelligence Platform',
  'description': 'Monitor competitor websites automatically. Track pricing changes, messaging shifts, and feature updates — then get AI-powered recommendations. Built for ecommerce brands and SaaS teams.',
  'isPartOf': { '@id': 'https://intelshift.ai/#website' },
  'about': { '@id': 'https://intelshift.ai/#software' },
  'speakable': {
    '@type': 'SpeakableSpecification',
    'cssSelector': ['h1', 'h2', '.hero-sub'],
  },
};

function Home() {
  return (
    <>
      <SEO
        title="AI-Powered Competitor Intelligence Platform"
        description="Monitor competitor websites automatically. Track pricing changes, messaging shifts, and feature updates — then get AI-powered recommendations. Built for ecommerce brands and SaaS teams."
        canonical="/"
        keywords="competitor intelligence software, competitor monitoring tool, competitor website tracking, AI competitor analysis, ecommerce competitor monitoring, SaaS competitor tracking, competitor pricing alerts, monitor competitor changes, competitive intelligence platform, competitor change detection, competitor website monitor"
        structuredData={homeStructuredData}
      />
      <Hero />
      <LongMarquee />
      <Problem />
      <HowItWorks />
      <ProductIntelligence />
      <FeaturesGrid />
      <UseCases />
      <Demo />
      <Trust />
      <Pricing />
      <Faq />
      <FinalCTA />
    </>
  );
}

export default Home;
