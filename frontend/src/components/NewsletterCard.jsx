import { motion } from 'framer-motion'
import { ExternalLink, Calendar, Globe } from 'lucide-react'

const CATEGORY_COLORS = {
  'Global': { bg: 'rgba(37,99,235,0.12)', text: '#60a5fa', border: 'rgba(37,99,235,0.2)' },
  'Politics': { bg: 'rgba(239,68,68,0.1)', text: '#f87171', border: 'rgba(239,68,68,0.2)' },
  'Business': { bg: 'rgba(34,197,94,0.1)', text: '#4ade80', border: 'rgba(34,197,94,0.2)' },
  'Technology': { bg: 'rgba(124,58,237,0.1)', text: '#a78bfa', border: 'rgba(124,58,237,0.2)' },
  'Science': { bg: 'rgba(6,182,212,0.1)', text: '#22d3ee', border: 'rgba(6,182,212,0.2)' },
  'Sports': { bg: 'rgba(245,158,11,0.1)', text: '#fbbf24', border: 'rgba(245,158,11,0.2)' },
}

export default function NewsletterCard({ article, index = 0 }) {
  const { title, summary, source, url, category, date } = article
  const colors = CATEGORY_COLORS[category] || CATEGORY_COLORS['Global']

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.05, ease: [0.16, 1, 0.3, 1] }}
      className="group relative flex flex-col h-full card p-5 hover:shadow-card-hover transition-all duration-300 hover:-translate-y-0.5"
    >
      {/* Category + Date */}
      <div className="flex items-center justify-between mb-3">
        <span
          className="text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full"
          style={{ background: colors.bg, color: colors.text, border: `1px solid ${colors.border}` }}
        >
          {category}
        </span>
        <span className="text-[10px] text-muted flex items-center gap-1">
          <Calendar size={9} />
          {date}
        </span>
      </div>

      {/* Title */}
      <h3 className="font-semibold text-[14px] text-slate-200 leading-snug mb-2.5 group-hover:text-white transition-colors line-clamp-2">
        {title}
      </h3>

      {/* Summary */}
      <p className="text-[12px] text-muted-light leading-relaxed flex-1 line-clamp-3 mb-4">
        {summary}
      </p>

      {/* Footer */}
      <div className="flex items-center justify-between pt-3 border-t border-white/[0.06]">
        <div className="flex items-center gap-1.5 text-[11px] text-muted">
          <Globe size={11} />
          <span>{source}</span>
        </div>
        {url ? (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-[11px] font-semibold text-primary-light hover:text-white transition-colors"
          >
            Read More
            <ExternalLink size={10} />
          </a>
        ) : (
          <button className="flex items-center gap-1 text-[11px] font-semibold text-primary-light hover:text-white transition-colors">
            Read More
            <ExternalLink size={10} />
          </button>
        )}
      </div>
    </motion.article>
  )
}
