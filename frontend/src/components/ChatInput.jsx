import { useState, useRef, useCallback } from 'react'
import { Send, Link2, Upload, FileJson, FileCode, Image, X, Loader2 } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const ATTACH_TYPES = [
  { id: 'url', icon: Link2, label: 'Paste URL', placeholder: 'https://...' },
  { id: 'json', icon: FileJson, label: 'Upload JSON', accept: '.json' },
  { id: 'html', icon: FileCode, label: 'Upload HTML', accept: '.html,.htm' },
  { id: 'image', icon: Image, label: 'Screenshot', accept: 'image/*' },
]

export default function ChatInput({ onSend, isLoading }) {
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState([])
  const [urlMode, setUrlMode] = useState(false)
  const textRef = useRef(null)
  const fileInputRef = useRef(null)
  const [pendingFileType, setPendingFileType] = useState(null)

  const autoResize = () => {
    const el = textRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = Math.min(el.scrollHeight, 200) + 'px'
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleSend = useCallback(() => {
    const trimmed = text.trim()
    if (!trimmed && attachments.length === 0) return
    if (isLoading) return
    onSend({ text: trimmed, attachments })
    setText('')
    setAttachments([])
    if (textRef.current) textRef.current.style.height = 'auto'
  }, [text, attachments, isLoading, onSend])

  const removeAttachment = (idx) => {
    setAttachments(prev => prev.filter((_, i) => i !== idx))
  }

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    setAttachments(prev => [...prev, { type: pendingFileType, file, name: file.name }])
    e.target.value = ''
  }

  const triggerFile = (type, accept) => {
    setPendingFileType(type)
    if (fileInputRef.current) {
      fileInputRef.current.accept = accept
      fileInputRef.current.click()
    }
  }

  const isUrl = text.trim().startsWith('http')
  const canSend = (text.trim().length > 0 || attachments.length > 0) && !isLoading

  return (
    <div className="px-4 pb-4">
      <div className="glass rounded-2xl border border-white/[0.09] overflow-hidden transition-all focus-within:border-primary/30 focus-within:shadow-glow-primary">
        {/* Attachments */}
        <AnimatePresence>
          {attachments.length > 0 && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-4 pt-3 flex flex-wrap gap-2"
            >
              {attachments.map((att, i) => (
                <div key={i} className="flex items-center gap-1.5 text-[12px] px-2.5 py-1 rounded-lg glass-primary text-primary-light">
                  <span className="truncate max-w-[140px]">{att.name}</span>
                  <button onClick={() => removeAttachment(i)} className="flex-shrink-0 hover:text-white">
                    <X size={11} />
                  </button>
                </div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {/* URL Detection Banner */}
        <AnimatePresence>
          {isUrl && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              className="px-4 pt-3"
            >
              <div className="flex items-center gap-2 text-[11px] text-primary-light px-2.5 py-1.5 rounded-lg glass-primary">
                <Link2 size={11} />
                <span>URL detected — will be analyzed with the news pipeline</span>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Textarea */}
        <div className="px-4 pt-3 pb-2">
          <textarea
            ref={textRef}
            value={text}
            onChange={e => { setText(e.target.value); autoResize() }}
            onKeyDown={handleKeyDown}
            placeholder="Paste a URL, ask a question, or describe what you want to analyze…"
            rows={1}
            className="chat-textarea"
            style={{ minHeight: 40, maxHeight: 200 }}
          />
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-3 pb-3">
          <div className="flex items-center gap-1 flex-1">
            {ATTACH_TYPES.map(({ id, icon: Icon, label, accept }) => (
              <button
                key={id}
                onClick={() => accept ? triggerFile(id, accept) : null}
                title={label}
                className="flex items-center gap-1.5 text-[11px] text-muted hover:text-slate-300 px-2.5 py-1.5 rounded-lg hover:bg-white/[0.05] transition-all"
              >
                <Icon size={13} />
                <span className="hidden sm:inline">{label}</span>
              </button>
            ))}
          </div>
          <button
            onClick={handleSend}
            disabled={!canSend}
            className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all ${
              canSend
                ? 'btn-primary'
                : 'bg-white/[0.05] text-muted cursor-not-allowed'
            }`}
          >
            {isLoading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <Send size={15} />
            )}
            <span className="hidden sm:inline">{isLoading ? 'Analyzing…' : 'Send'}</span>
          </button>
        </div>
      </div>
      <p className="text-[10px] text-muted text-center mt-2">
        Press <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-muted-light">Enter</kbd> to send · <kbd className="px-1 py-0.5 rounded bg-white/[0.06] text-muted-light">Shift+Enter</kbd> for new line
      </p>

      <input
        ref={fileInputRef}
        type="file"
        className="hidden"
        onChange={handleFileChange}
      />
    </div>
  )
}
