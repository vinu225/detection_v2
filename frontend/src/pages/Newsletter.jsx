import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { NavLink } from 'react-router-dom'
import { Newspaper, RefreshCw, Zap, Calendar, ChevronLeft } from 'lucide-react'
import NewsletterCard from '@/components/NewsletterCard'
import Sidebar from '@/components/Sidebar'

const today = new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })

const NEWSLETTER_DATA = {
  Global: [
    {
      title: 'UN Security Council Holds Emergency Session on Gaza Ceasefire',
      summary: 'World leaders convene as death toll surpasses 42,000. The session is expected to produce a binding resolution calling for an immediate cessation of hostilities and unimpeded humanitarian access.',
      source: 'Reuters', category: 'Global', date: 'Jun 19'
    },
    {
      title: 'G7 Leaders Agree on $50 Billion Ukraine Aid Package',
      summary: "The package, backed by Russia's frozen assets, represents the largest single financial commitment to Ukraine since the conflict began. European leaders pledged to accelerate delivery of air defense systems.",
      source: 'BBC News', category: 'Global', date: 'Jun 19'
    },
    {
      title: 'WHO Declares New Disease Outbreak in West Africa',
      summary: 'Health officials are racing to contain a novel hemorrhagic fever detected in three countries. Emergency response teams have been deployed and travel advisories are expected.',
      source: 'AP News', category: 'Global', date: 'Jun 19'
    },
  ],
  Politics: [
    {
      title: 'US Senate Passes Landmark Immigration Reform Bill',
      summary: 'The bill, which passed 58-42, includes pathways to citizenship for 3 million undocumented immigrants and significant border security investments. It now heads to the House.',
      source: 'Politico', category: 'Politics', date: 'Jun 19'
    },
    {
      title: 'Indian Parliament Debates New Digital Governance Framework',
      summary: 'Opposition parties raise concerns over data privacy provisions in the proposed legislation. The ruling coalition expects the bill to pass by the end of the monsoon session.',
      source: 'The Hindu', category: 'Politics', date: 'Jun 18'
    },
    {
      title: 'European Parliament Elects New President Amid Fractured Alliances',
      summary: 'The vote required four rounds before a majority emerged. The new leadership will face immediate challenges including EU enlargement negotiations and green deal implementation.',
      source: 'Euronews', category: 'Politics', date: 'Jun 18'
    },
  ],
  Business: [
    {
      title: 'NVIDIA Hits $4 Trillion Valuation — Largest Company in History',
      summary: "Driven by insatiable demand for AI computing infrastructure, NVIDIA's market capitalization surpassed Apple and Microsoft. CEO Jensen Huang announced a 10-for-1 stock split.",
      source: 'Bloomberg', category: 'Business', date: 'Jun 19'
    },
    {
      title: 'Federal Reserve Signals Three Rate Cuts for Second Half of 2025',
      summary: 'Inflation data coming in below the 2.5% threshold gave policymakers confidence to begin easing. Markets rallied sharply on the announcement, with the S&P 500 gaining 2.1%.',
      source: 'Wall Street Journal', category: 'Business', date: 'Jun 19'
    },
    {
      title: 'Amazon Acquires Nuclear Power Startup for $2.8 Billion',
      summary: "The deal underscores Big Tech's growing appetite for carbon-free baseload energy to power AI data centers. The acquisition includes two operational small modular reactor projects.",
      source: 'Financial Times', category: 'Business', date: 'Jun 18'
    },
  ],
  Technology: [
    {
      title: "Google DeepMind's Gemini Ultra 2.0 Achieves Human-Level Reasoning on Key Benchmarks",
      summary: 'The new model surpasses previous state-of-the-art on mathematical reasoning, code generation, and scientific problem-solving. Access will be rolled out to enterprise customers first.',
      source: 'The Verge', category: 'Technology', date: 'Jun 19'
    },
    {
      title: 'OpenAI Launches GPT-5 Turbo with 1M Context Window',
      summary: 'The model can process entire codebases and research corpora in a single prompt. A new memory architecture allows persistent context across sessions at no additional cost.',
      source: 'TechCrunch', category: 'Technology', date: 'Jun 19'
    },
    {
      title: 'Apple Vision Pro 2 Announced with 40% Lower Price Point',
      summary: 'The second-generation spatial computer features a lighter form factor, longer battery life, and expanded developer ecosystem. Pre-orders open next week.',
      source: '9to5Mac', category: 'Technology', date: 'Jun 18'
    },
  ],
  Science: [
    {
      title: 'Scientists Achieve Room-Temperature Superconductivity Under Modest Pressure',
      summary: 'Researchers at MIT and ETH Zürich jointly announced the breakthrough, which could transform electrical infrastructure, magnetic resonance imaging, and quantum computing.',
      source: 'Nature', category: 'Science', date: 'Jun 19'
    },
    {
      title: 'Mars Sample Return Mission Receives $2.1 Billion in Emergency Funding',
      summary: 'NASA and ESA announced a restructured mission architecture designed to retrieve Perseverance rover samples by 2033. The new plan eliminates the previously canceled Earth Entry Vehicle.',
      source: 'Space.com', category: 'Science', date: 'Jun 18'
    },
    {
      title: 'CRISPR Gene Therapy Cures Sickle Cell Disease in Large Clinical Trial',
      summary: '94% of trial participants were symptom-free after 24 months. The FDA is expected to review the application for full approval within six months.',
      source: 'STAT News', category: 'Science', date: 'Jun 18'
    },
  ],
  Sports: [
    {
      title: 'Team India Wins ICC Champions Trophy 2025 in Thrilling Final',
      summary: 'Rohit Sharma led India to a 7-wicket victory over Australia in the final, with Shubman Gill scoring a brilliant century. The win ends a decade-long ICC title drought.',
      source: 'ESPNCricinfo', category: 'Sports', date: 'Jun 19'
    },
    {
      title: 'Carlos Alcaraz Claims Third Consecutive Wimbledon Title',
      summary: 'The Spanish superstar defeated Jannik Sinner in five sets in a match widely described as one of the greatest finals in the tournament\'s 147-year history.',
      source: 'Tennis.com', category: 'Sports', date: 'Jun 18'
    },
    {
      title: 'FIFA World Cup 2026 Draw Reveals "Group of Death"',
      summary: 'Brazil, France, and Portugal are drawn into the same group alongside Japan. Football analysts predict this will be the most competitive group stage in World Cup history.',
      source: 'ESPN', category: 'Sports', date: 'Jun 18'
    },
  ],
}

const SECTIONS = Object.keys(NEWSLETTER_DATA)

export default function Newsletter() {
  const [activeSection, setActiveSection] = useState('Global')
  const [isGenerating, setIsGenerating] = useState(false)
  const [generated, setGenerated] = useState(true)

  const handleGenerate = () => {
    setIsGenerating(true)
    setGenerated(false)
    setTimeout(() => {
      setIsGenerating(false)
      setGenerated(true)
    }, 1800)
  }

  return (
    <div className="flex h-screen overflow-hidden relative">
      <div className="orb-1" />
      <div className="orb-2" />

      {/* Sidebar */}
      <div className="hidden lg:flex w-[280px] flex-shrink-0 relative z-10">
        <Sidebar />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative z-10">
        {/* Header */}
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-white/[0.06]">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center">
                  <Newspaper size={15} className="text-white" />
                </div>
                <h1 className="font-display text-xl font-bold text-white">Today's AI Newsletter</h1>
              </div>
              <div className="flex items-center gap-2 text-[12px] text-muted ml-10">
                <Calendar size={11} />
                <span>{today}</span>
                <span className="text-white/20">·</span>
                <span className="text-success flex items-center gap-1">
                  <Zap size={10} />
                  AI-generated
                </span>
              </div>
            </div>
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex items-center gap-2 px-4 py-2 rounded-xl btn-primary text-sm font-semibold flex-shrink-0"
            >
              <RefreshCw size={14} className={isGenerating ? 'animate-spin' : ''} />
              {isGenerating ? 'Generating…' : "Generate Today's"}
            </button>
          </div>

          {/* Section Tabs */}
          <div className="flex items-center gap-1 mt-4 overflow-x-auto pb-1">
            {SECTIONS.map(section => (
              <button
                key={section}
                onClick={() => setActiveSection(section)}
                className={`flex-shrink-0 px-4 py-1.5 rounded-lg text-[12px] font-semibold transition-all ${
                  activeSection === section
                    ? 'glass-primary text-primary-light'
                    : 'text-muted hover:text-slate-300 hover:bg-white/[0.04]'
                }`}
              >
                {section}
              </button>
            ))}
          </div>
        </div>

        {/* Cards Grid */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <AnimatePresence mode="wait">
            {isGenerating ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
              >
                {[1, 2, 3].map(i => (
                  <div key={i} className="card p-5 h-52 shimmer-bg animate-pulse" />
                ))}
              </motion.div>
            ) : (
              <motion.div
                key={activeSection}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.25 }}
                className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4"
              >
                {(NEWSLETTER_DATA[activeSection] || []).map((article, i) => (
                  <NewsletterCard key={i} article={article} index={i} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          <p className="text-center text-[11px] text-muted mt-8 pb-4">
            Weekly newsletter — coming soon
          </p>
        </div>
      </div>
    </div>
  )
}
