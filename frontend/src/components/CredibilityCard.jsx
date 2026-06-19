import { motion } from 'framer-motion'
import { ShieldCheck, ShieldAlert, ShieldX, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'

function ArcMeter({ score }) {
  const r = 36
  const circumference = Math.PI * r  // half circle
  const fraction = score / 100
  const color = score >= 70 ? '#22C55E' : score >= 40 ? '#F59E0B' : '#EF4444'
  const dashOffset = circumference * (1 - fraction)

  return (
    <div className="relative flex items-center justify-center" style={{ width: 92, height: 52 }}>
      <svg width="92" height="52" viewBox="0 0 92 52">
        {/* Track */}
        <path
          d="M 8 46 A 38 38 0 0 1 84 46"
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth="8"
          strokeLinecap="round"
        />
        {/* Filled arc */}
        <motion.path
          d="M 8 46 A 38 38 0 0 1 84 46"
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 1.2, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <div className="absolute bottom-0 flex flex-col items-center">
        <span className="text-xl font-bold leading-none" style={{ color }}>{score}</span>
        <span className="text-[9px] text-muted mt-0.5">/ 100</span>
      </div>
    </div>
  )
}

const FACTORS = {
  high: [
    { icon: CheckCircle2, text: 'Known reputable source', positive: true },
    { icon: CheckCircle2, text: 'Author byline present', positive: true },
    { icon: AlertTriangle, text: 'Emotional language detected', positive: false },
    { icon: XCircle, text: 'Missing supporting citations', positive: false },
  ],
  medium: [
    { icon: CheckCircle2, text: 'Source verified', positive: true },
    { icon: AlertTriangle, text: 'Emotional wording found', positive: false },
    { icon: XCircle, text: 'High negative sentiment', positive: false },
    { icon: XCircle, text: 'Missing supporting evidence', positive: false },
  ],
  low: [
    { icon: XCircle, text: 'Unverified source', positive: false },
    { icon: XCircle, text: 'Extreme emotional framing', positive: false },
    { icon: XCircle, text: 'No citations provided', positive: false },
    { icon: AlertTriangle, text: 'Contradicts established facts', positive: false },
  ]
}

export default function CredibilityCard({ data }) {
  const score = data?.credibility_score ?? 82
  const color = score >= 70 ? '#22C55E' : score >= 40 ? '#F59E0B' : '#EF4444'
  const label = score >= 70 ? 'High Credibility' : score >= 40 ? 'Moderate' : 'Low Credibility'
  const Icon = score >= 70 ? ShieldCheck : score >= 40 ? ShieldAlert : ShieldX
  const factorKey = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low'
  const factors = data?.factors || FACTORS[factorKey]

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="rounded-xl overflow-hidden border border-white/[0.07]"
      style={{ background: 'rgba(15, 23, 42, 0.5)' }}
    >
      <div className="flex items-center gap-2 px-4 py-3 border-b border-white/[0.06]">
        <Icon size={14} style={{ color }} />
        <span className="text-xs font-semibold text-slate-300 uppercase tracking-wider">Credibility Score</span>
      </div>

      <div className="px-4 py-4">
        <div className="flex items-center gap-5 mb-4">
          <ArcMeter score={score} />
          <div>
            <p className="font-bold text-lg leading-tight" style={{ color }}>{label}</p>
            <p className="text-xs text-muted mt-1">Based on source, language & evidence analysis</p>
          </div>
        </div>

        {/* Factors */}
        <div className="space-y-1.5">
          {factors.map((f, i) => {
            const FIcon = f.icon
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 + i * 0.08 }}
                className="flex items-center gap-2 text-[12px]"
              >
                <FIcon size={12} className={f.positive ? 'text-success' : 'text-danger'} />
                <span className={f.positive ? 'text-slate-300' : 'text-slate-400'}>{f.text}</span>
              </motion.div>
            )
          })}
        </div>
      </div>
    </motion.div>
  )
}
