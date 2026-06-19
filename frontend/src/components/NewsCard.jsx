import { motion } from 'framer-motion'
import { ExternalLink, ArrowRight, Globe, Calendar } from 'lucide-react'

const SENTIMENT_STYLE = {
  Positive: 'badge-positive',
  Neutral: 'badge-neutral',
  Negative: 'badge-negative',
}

const CATEGORY_COLORS = {
  'Politics': { bg: 'rgba(239,68,68,0.08)', text: '#f87171', border: 'rgba(239,68,68,0.15)' },
  'Technology': { bg: 'rgba(124,58,237,0.08)', text: '#a78bfa', border: 'rgba(124,58,237,0.15)' },
  'Business': { bg: 'rgba(34,197,94,0.08)', text: '#4ade80', border: 'rgba(34,197,94,0.15)' },
  'Sports': { bg: 'rgba(245,158,11,0.08)', text: '#fbbf24', border: 'rgba(245,158,11,0.15)' },
  'Science': { bg: 'rgba(6,182,212,0.08)', text: '#22d3ee', border: 'rgba(6,182,212,0.15)' },
  'Entertainment': { bg: 'rgba(236,72,153,0.08)', text: '#f472b6', border: 'rgba(236,72,153,0.15)' },
  'All': { bg: 'rgba(37,99,235,0.08)', text: '#60a5fa', border: 'rgba(37,99,235,0.15)' },
}

export default function NewsCard({ article, index = 0, onAnalyze }) {
  const { headline, source, date, category, sentiment, url } = article
  const catColors = CATEGORY_COLORS[category] || CATEGORY_COLORS['All']
  const sentimentClass = SENTIMENT_STYLE[sentiment] || SENTIMENT_STYLE.Neutral

  return (
    <motion.article
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.38, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
      className="group card p-4 flex flex-col gap-3 hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-300"
    >
      {/* Badges row */}
      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="badge-category text-[10px]"
          style={{ background: catColors.bg, color: catColors.text, border: `1px solid ${catColors.border}` }}
        >
          {category}
        </span>
        <span className={`badge-category text-[10px] ${sentimentClass}`}>
          {sentiment}
        </span>
      </div>

      {/* Headline */}
      <h3 className="text-[13px] font-semibold text-slate-200 leading-snug group-hover:text-white transition-colors line-clamp-3">
        {headline}
      </h3>

      {/* Meta */}
      <div className="flex items-center gap-3 text-[11px] text-muted mt-auto">
        <span className="flex items-center gap-1">
          <Globe size={10} />
          {source}
        </span>
        <span className="flex items-center gap-1">
          <Calendar size={10} />
          {date}
        </span>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-2 border-t border-white/[0.05]">
        <button
          onClick={() => onAnalyze?.(article)}
          className="flex-1 flex items-center justify-center gap-1.5 text-[11px] font-semibold text-primary-light hover:text-white bg-primary/10 hover:bg-primary/20 border border-primary/20 py-1.5 rounded-lg transition-all"
        >
          <ExternalLink size={11} />
          Open Analysis
        </button>
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 rounded-lg hover:bg-white/[0.05] text-muted hover:text-slate-300 transition-colors"
          >
            <ArrowRight size={13} />
          </a>
        )}
      </div>
    </motion.article>
  )
}
