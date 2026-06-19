import { motion, AnimatePresence } from 'framer-motion'
import { TrendingUp, BarChart2, ShieldCheck, AlertCircle } from 'lucide-react'

const SENTIMENT_COLOR = {
  Positive: { text: 'text-success', bg: 'badge-positive', bar: '#22C55E' },
  Neutral: { text: 'text-warning', bg: 'badge-neutral', bar: '#F59E0B' },
  Negative: { text: 'text-danger', bg: 'badge-negative', bar: '#EF4444' },
}

function ProgressBar({ value, color, label, pct }) {
  return (
    <div className="space-y-1.5">
      <div className="flex justify-between items-center">
        <span className="text-xs text-muted-light">{label}</span>
        <span className="text-xs font-semibold" style={{ color }}>{pct}%</span>
      </div>
      <div className="progress-bar">
        <motion.div
          className="progress-fill"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />
      </div>
    </div>
  )
}

function IntensityGauge({ value }) {
  const r = 28
  const circumference = 2 * Math.PI * r
  const filled = (value / 100) * circumference
  const color = value >= 70 ? '#EF4444' : value >= 40 ? '#F59E0B' : '#22C55E'

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative w-[72px] h-[72px]">
        <svg width="72" height="72" viewBox="0 0 72 72">
          <circle
            cx="36" cy="36" r={r}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="6"
          />
          <motion.circle
            cx="36" cy="36" r={r}
            fill="none"
            stroke={color}
            strokeWidth="6"
            strokeLinecap="round"
            strokeDasharray={circumference}
            className="gauge-ring"
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: circumference - filled }}
            transition={{ duration: 1, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-base font-bold" style={{ color }}>{value}</span>
        </div>
      </div>
      <span className="text-[10px] text-muted text-center leading-tight">Emotional<br />Intensity</span>
    </div>
  )
}

export default function SentimentCard({ data }) {
  const headline = data?.headline_sentiment || { label: 'Negative', score: 91 }
  const article = data?.article_sentiment || { label: 'Neutral', score: 82 }
  const intensity = data?.emotional_intensity ?? 72

  const hlColors = SENTIMENT_COLOR[headline.label] || SENTIMENT_COLOR.Neutral
  const arColors = SENTIMENT_COLOR[article.label] || SENTIMENT_COLOR.Neutral

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="rounded-xl overflow-hidden border border-white/[0.07]"
      style={{ background: 'rgba(15, 23, 42, 0.5)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
        <BarChart2 size={14} className="text-primary-light" />
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Sentiment Analysis</span>
      </div>
      <div className="px-4 py-4 space-y-4">
        {/* Headline Sentiment */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] text-muted uppercase tracking-wider font-semibold mb-1">Headline Sentiment</p>
            <span className={`badge-category ${hlColors.bg} text-[11px] px-2 py-0.5 rounded-full`}>
              {headline.label} ({headline.score}%)
            </span>
          </div>
          {headline.label === 'Negative' && <AlertCircle size={20} className="text-danger opacity-70" />}
          {headline.label === 'Positive' && <TrendingUp size={20} className="text-success opacity-70" />}
        </div>

        {/* Article Sentiment bar */}
        <div>
          <p className="text-[11px] text-muted uppercase tracking-wider font-semibold mb-2">Article Sentiment</p>
          <ProgressBar
            label={article.label}
            pct={article.score}
            color={arColors.bar}
          />
        </div>

        {/* Emotional Intensity gauge */}
        <div className="flex items-center gap-4">
          <IntensityGauge value={intensity} />
          <div className="flex-1 text-xs text-muted-light leading-relaxed">
            Emotional language intensity score. Values above 70 indicate highly charged content.
          </div>
        </div>
      </div>
    </motion.div>
  )
}
