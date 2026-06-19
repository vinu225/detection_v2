import { motion } from 'framer-motion'
import { Sparkles, ExternalLink, FileText, Clock } from 'lucide-react'
import SentimentCard from './SentimentCard'
import CredibilityCard from './CredibilityCard'

export default function AnalysisCard({ message }) {
  const { data, query } = message

  const summary = data?.answer || data?.news_analysis || data?.summary || 'Analysis complete.'
  const sentimentData = data?.sentiment || null
  const credibilityData = data?.credibility || null
  const sources = data?.context_sources || []
  const articles = data?.articles || []

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-3 max-w-full"
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        <div className="w-7 h-7 rounded-lg gradient-primary flex items-center justify-center flex-shrink-0">
          <Sparkles size={13} className="text-white" />
        </div>
        <span className="text-[13px] font-semibold text-slate-300">AetherNews AI</span>
        <span className="text-[11px] text-muted ml-auto flex items-center gap-1">
          <Clock size={10} />
          {new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </span>
      </div>

      {/* Summary */}
      <div className="msg-ai px-4 py-3.5 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
        {summary}
      </div>

      {/* Sentiment + Credibility side-by-side on wider screens */}
      {(sentimentData !== null || !data?.answer) && (
        <div className="grid grid-cols-1 gap-3">
          <SentimentCard data={sentimentData} />
          <CredibilityCard data={credibilityData} />
        </div>
      )}

      {/* Articles ingested */}
      {articles.length > 0 && (
        <div className="rounded-xl border border-white/[0.07] overflow-hidden" style={{ background: 'rgba(15, 23, 42, 0.5)' }}>
          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]">
            <FileText size={13} className="text-primary-light" />
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              Ingested Articles ({articles.length})
            </span>
          </div>
          <div className="divide-y divide-white/[0.04]">
            {articles.slice(0, 5).map((art, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.1 + i * 0.06 }}
                className="px-4 py-2.5 flex items-start justify-between gap-3 hover:bg-white/[0.02] transition-colors"
              >
                <div className="min-w-0">
                  <p className="text-[12px] text-slate-300 font-medium truncate">{art.title}</p>
                  <p className="text-[11px] text-muted mt-0.5">{art.source}</p>
                </div>
                {art.url && (
                  <a href={art.url} target="_blank" rel="noopener noreferrer"
                    className="flex-shrink-0 text-primary-light hover:text-primary transition-colors">
                    <ExternalLink size={12} />
                  </a>
                )}
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Sources */}
      {sources.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {sources.map((src, i) => (
            <span key={i} className="text-[10px] px-2 py-1 rounded-full border border-white/[0.08] text-muted bg-white/[0.03]">
              {src}
            </span>
          ))}
        </div>
      )}
    </motion.div>
  )
}
