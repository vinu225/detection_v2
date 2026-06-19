import { useState, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, TrendingUp, Filter, X } from 'lucide-react'
import NewsCard from '@/components/NewsCard'
import Sidebar from '@/components/Sidebar'
import { useNavigate } from 'react-router-dom'

const TOP_NEWS = [
  { id: 1, headline: 'NVIDIA Surpasses $4 Trillion Market Cap in Historic Tech Rally', source: 'Bloomberg', date: 'Jun 19', category: 'Business', sentiment: 'Positive', country: 'US' },
  { id: 2, headline: 'WHO Declares Emergency Over Novel Hemorrhagic Fever in West Africa', source: 'Reuters', date: 'Jun 19', category: 'Science', sentiment: 'Negative', country: 'Global' },
  { id: 3, headline: 'Federal Reserve Signals Three Rate Cuts in Second Half of 2025', source: 'Wall Street Journal', date: 'Jun 19', category: 'Business', sentiment: 'Positive', country: 'US' },
  { id: 4, headline: 'India Wins ICC Champions Trophy 2025 — Rohit Sharma Era Peaks', source: 'ESPNCricinfo', date: 'Jun 19', category: 'Sports', sentiment: 'Positive', country: 'India' },
  { id: 5, headline: 'Apple Vision Pro 2 Unveiled with 40% Lower Starting Price', source: 'TechCrunch', date: 'Jun 19', category: 'Technology', sentiment: 'Positive', country: 'US' },
  { id: 6, headline: 'UN Security Council Convenes Emergency Session on Gaza', source: 'Al Jazeera', date: 'Jun 19', category: 'Politics', sentiment: 'Negative', country: 'Global' },
  { id: 7, headline: 'Scientists Achieve Room-Temperature Superconductivity', source: 'Nature', date: 'Jun 19', category: 'Science', sentiment: 'Positive', country: 'Global' },
  { id: 8, headline: 'OpenAI Launches GPT-5 Turbo with 1 Million Token Context Window', source: 'The Verge', date: 'Jun 18', category: 'Technology', sentiment: 'Positive', country: 'US' },
  { id: 9, headline: 'G7 Finalizes $50B Ukraine Aid Deal Using Frozen Russian Assets', source: 'BBC', date: 'Jun 18', category: 'Politics', sentiment: 'Neutral', country: 'Europe' },
  { id: 10, headline: 'Amazon Acquires Nuclear Power Startup for $2.8 Billion', source: 'Financial Times', date: 'Jun 18', category: 'Business', sentiment: 'Positive', country: 'US' },
  { id: 11, headline: 'Carlos Alcaraz Claims Third Consecutive Wimbledon Title', source: 'ESPN', date: 'Jun 18', category: 'Sports', sentiment: 'Positive', country: 'UK' },
  { id: 12, headline: 'CRISPR Gene Therapy Achieves 94% Success Rate in Sickle Cell Trial', source: 'STAT News', date: 'Jun 18', category: 'Science', sentiment: 'Positive', country: 'US' },
  { id: 13, headline: 'Pakistan Floods Kill 340 as Monsoon Season Intensifies', source: 'Reuters', date: 'Jun 18', category: 'Global', sentiment: 'Negative', country: 'Global' },
  { id: 14, headline: 'EU Passes Landmark AI Liability Directive', source: 'Euronews', date: 'Jun 18', category: 'Technology', sentiment: 'Neutral', country: 'Europe' },
  { id: 15, headline: 'India Surpasses Japan to Become World\'s Third Largest Economy', source: 'The Hindu', date: 'Jun 17', category: 'Business', sentiment: 'Positive', country: 'India' },
  { id: 16, headline: 'SpaceX Starship Completes First Successful Orbital Mission', source: 'Space.com', date: 'Jun 17', category: 'Science', sentiment: 'Positive', country: 'US' },
  { id: 17, headline: 'UK General Election Results Reshape Conservative Party', source: 'The Guardian', date: 'Jun 17', category: 'Politics', sentiment: 'Neutral', country: 'UK' },
  { id: 18, headline: 'FIFA 2026 World Cup Draw Reveals "Group of Death"', source: 'ESPN', date: 'Jun 17', category: 'Sports', sentiment: 'Neutral', country: 'Global' },
  { id: 19, headline: 'Bitcoin Hits New All-Time High Above $120,000', source: 'CoinDesk', date: 'Jun 17', category: 'Business', sentiment: 'Positive', country: 'Global' },
  { id: 20, headline: 'Meta Releases Llama 4 Open-Source Model — Outperforms GPT-4', source: 'VentureBeat', date: 'Jun 17', category: 'Technology', sentiment: 'Positive', country: 'US' },
  { id: 21, headline: 'Iran Nuclear Deal Talks Resume in Vienna', source: 'AP News', date: 'Jun 16', category: 'Politics', sentiment: 'Neutral', country: 'Global' },
  { id: 22, headline: 'Chinese EV Sales Surpass ICE Vehicles for First Time', source: 'Bloomberg', date: 'Jun 16', category: 'Business', sentiment: 'Positive', country: 'Global' },
  { id: 23, headline: 'Amazon Workers Strike Across 20 Countries in Coordinated Action', source: 'Reuters', date: 'Jun 16', category: 'Business', sentiment: 'Negative', country: 'Global' },
  { id: 24, headline: 'Deepfake Detection Becomes Mandatory Under New US Law', source: 'Wired', date: 'Jun 16', category: 'Technology', sentiment: 'Neutral', country: 'US' },
  { id: 25, headline: 'Tour de France 2025 Opens with Surprise Leader After Stage One', source: 'Cycling Weekly', date: 'Jun 15', category: 'Sports', sentiment: 'Neutral', country: 'Europe' },
]

const CATEGORIES = ['All', 'Politics', 'Technology', 'Business', 'Sports', 'Science', 'Entertainment']
const SOURCES = ['All', 'Reuters', 'BBC', 'CNN', 'AP', 'Al Jazeera']
const COUNTRIES = ['All', 'US', 'UK', 'India', 'Europe', 'Global']

function FilterChip({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex-shrink-0 px-3 py-1.5 rounded-lg text-[12px] font-semibold transition-all ${
        active
          ? 'glass-primary text-primary-light'
          : 'text-muted hover:text-slate-300 hover:bg-white/[0.04] border border-transparent'
      }`}
    >
      {label}
    </button>
  )
}

export default function TopNews() {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('All')
  const [source, setSource] = useState('All')
  const [country, setCountry] = useState('All')
  const navigate = useNavigate()

  const filtered = useMemo(() => {
    return TOP_NEWS.filter(a => {
      const matchesQuery = !query || a.headline.toLowerCase().includes(query.toLowerCase()) || a.source.toLowerCase().includes(query.toLowerCase())
      const matchesCat = category === 'All' || a.category === category
      const matchesSrc = source === 'All' || a.source.includes(source)
      const matchesCountry = country === 'All' || a.country === country
      return matchesQuery && matchesCat && matchesSrc && matchesCountry
    })
  }, [query, category, source, country])

  const handleAnalyze = (article) => {
    navigate('/dashboard', { state: { analyzeArticle: article } })
  }

  const clearFilters = () => {
    setQuery('')
    setCategory('All')
    setSource('All')
    setCountry('All')
  }

  const hasFilters = query || category !== 'All' || source !== 'All' || country !== 'All'

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
          <div className="flex items-center gap-3 mb-4">
            <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center">
              <TrendingUp size={15} className="text-white" />
            </div>
            <div>
              <h1 className="font-display text-xl font-bold text-white leading-tight">Top 100 News</h1>
              <p className="text-[11px] text-muted">Live trending stories from global sources</p>
            </div>
            <div className="ml-auto flex items-center gap-2 text-[11px] text-muted">
              <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
              {filtered.length} articles
            </div>
          </div>

          {/* Search */}
          <div className="flex items-center gap-2 px-4 py-2.5 rounded-xl glass border-white/[0.08] mb-3">
            <Search size={14} className="text-muted flex-shrink-0" />
            <input
              type="text"
              placeholder="Search headlines, sources…"
              value={query}
              onChange={e => setQuery(e.target.value)}
              className="flex-1 bg-transparent border-none outline-none text-sm text-slate-300 placeholder-muted"
            />
            {query && (
              <button onClick={() => setQuery('')}>
                <X size={13} className="text-muted hover:text-white" />
              </button>
            )}
          </div>

          {/* Filters */}
          <div className="space-y-2">
            <div className="flex items-center gap-2 overflow-x-auto pb-1">
              <span className="text-[10px] text-muted font-semibold uppercase tracking-wider flex-shrink-0 flex items-center gap-1">
                <Filter size={9} /> Category
              </span>
              {CATEGORIES.map(c => (
                <FilterChip key={c} label={c} active={category === c} onClick={() => setCategory(c)} />
              ))}
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 overflow-x-auto pb-1 flex-1">
                <span className="text-[10px] text-muted font-semibold uppercase tracking-wider flex-shrink-0">Country</span>
                {COUNTRIES.map(c => (
                  <FilterChip key={c} label={c} active={country === c} onClick={() => setCountry(c)} />
                ))}
              </div>
              {hasFilters && (
                <button
                  onClick={clearFilters}
                  className="flex-shrink-0 text-[11px] text-danger hover:text-danger/80 font-medium flex items-center gap-1"
                >
                  <X size={11} /> Clear
                </button>
              )}
            </div>
          </div>
        </div>

        {/* News Grid */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <AnimatePresence mode="wait">
            {filtered.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="flex flex-col items-center justify-center h-48 text-center"
              >
                <TrendingUp size={32} className="text-muted mb-3 opacity-40" />
                <p className="text-muted text-sm">No articles match your filters</p>
                <button onClick={clearFilters} className="mt-3 text-xs text-primary-light hover:text-white">
                  Clear all filters
                </button>
              </motion.div>
            ) : (
              <motion.div
                key="grid"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                transition={{ duration: 0.2 }}
                className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-4"
              >
                {filtered.map((article, i) => (
                  <NewsCard
                    key={article.id}
                    article={article}
                    index={i}
                    onAnalyze={handleAnalyze}
                  />
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}
