import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Globe, FileText, BarChart2 } from 'lucide-react'
import AnalysisCard from './AnalysisCard'

const WELCOME_FEATURES = [
  { icon: Globe, title: 'Analyze any URL', desc: 'Paste a news link for instant analysis' },
  { icon: FileText, title: 'Upload documents', desc: 'JSON, HTML, or screenshot uploads' },
  { icon: BarChart2, title: 'Sentiment scoring', desc: 'Headline & article-level analysis' },
  { icon: Zap, title: 'AI-powered synthesis', desc: 'RAG-backed news intelligence' },
]

function WelcomeState() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col items-center justify-center h-full px-6 text-center"
    >
      <div className="w-16 h-16 rounded-2xl gradient-primary flex items-center justify-center mb-5 shadow-glow-primary animate-pulse-glow">
        <Zap size={28} className="text-white" />
      </div>
      <h2 className="font-display text-2xl font-bold text-white mb-2">Analyze News with AI</h2>
      <p className="text-muted-light text-sm max-w-sm leading-relaxed mb-10">
        Paste a URL, upload a file, or ask questions about news. Get instant sentiment analysis, credibility scores, and AI synthesis.
      </p>

      <div className="grid grid-cols-2 gap-3 w-full max-w-md">
        {WELCOME_FEATURES.map(({ icon: Icon, title, desc }, i) => (
          <motion.div
            key={title}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 + i * 0.08 }}
            className="card p-4 text-left hover:border-primary/20 cursor-default"
          >
            <div className="w-8 h-8 rounded-lg glass-primary flex items-center justify-center mb-2.5">
              <Icon size={14} className="text-primary-light" />
            </div>
            <p className="text-[13px] font-semibold text-slate-300 mb-0.5">{title}</p>
            <p className="text-[11px] text-muted leading-relaxed">{desc}</p>
          </motion.div>
        ))}
      </div>

      <div className="mt-10 flex items-center gap-3 text-xs text-muted">
        <span className="w-1.5 h-1.5 rounded-full bg-success animate-pulse" />
        Backend connected · FastAPI + MongoDB
      </div>
    </motion.div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div className="w-7 h-7 rounded-lg gradient-primary flex items-center justify-center flex-shrink-0 mt-0.5">
        <Zap size={13} className="text-white" />
      </div>
      <div className="msg-ai px-4 py-3.5 flex items-center gap-1.5">
        <span className="typing-dot" />
        <span className="typing-dot" />
        <span className="typing-dot" />
      </div>
    </div>
  )
}

export default function ChatWindow({ messages, isLoading }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  if (messages.length === 0) {
    return <WelcomeState />
  }

  return (
    <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 min-h-0">
      <AnimatePresence initial={false}>
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
          >
            {msg.role === 'user' ? (
              <div className="flex justify-end">
                <div className="msg-user px-4 py-3 text-sm text-slate-200 max-w-[80%] leading-relaxed">
                  {msg.content}
                </div>
              </div>
            ) : (
              <div className="flex items-start gap-3 max-w-full">
                <div className="flex-1 min-w-0">
                  {msg.type === 'analysis' ? (
                    <AnalysisCard message={msg} />
                  ) : (
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <div className="w-7 h-7 rounded-lg gradient-primary flex items-center justify-center">
                          <Zap size={13} className="text-white" />
                        </div>
                        <span className="text-[13px] font-semibold text-slate-300">AetherNews AI</span>
                      </div>
                      <div className="msg-ai px-4 py-3.5 text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                        {msg.content}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </motion.div>
        ))}
      </AnimatePresence>

      {isLoading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <TypingIndicator />
        </motion.div>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
