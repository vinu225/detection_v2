import { useState, useCallback, useId } from 'react'
import Sidebar from '@/components/Sidebar'
import ChatWindow from '@/components/ChatWindow'
import ChatInput from '@/components/ChatInput'
import { queryLLM, queryNews, runUnifiedPipeline, analyzeImage } from '@/services/api'
import { Menu, X } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

let msgCounter = 0
const uid = () => `msg-${++msgCounter}`

function detectInputType(input) {
  const { text, attachments } = input
  if (attachments?.some(a => a.type === 'image')) return 'image'
  if (attachments?.some(a => a.type === 'json' || a.type === 'html')) return 'file'
  if (text?.match(/^https?:\/\//)) return 'url'
  return 'text'
}

export default function Dashboard() {
  const [messages, setMessages] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  const [activeChat, setActiveChat] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)

  const addMessage = (msg) => setMessages(prev => [...prev, msg])

  const handleSend = useCallback(async (input) => {
    const { text, attachments } = input
    const displayText = text || (attachments?.[0]?.name ?? 'File uploaded')

    // Add user message
    addMessage({ id: uid(), role: 'user', content: displayText })
    setIsLoading(true)

    try {
      const inputType = detectInputType(input)
      let responseData = {}
      let msgType = 'analysis'

      if (inputType === 'image') {
        const fd = new FormData()
        fd.append('file', attachments[0].file)
        const res = await analyzeImage(fd)
        responseData = res.data
        msgType = 'analysis'
      } else if (inputType === 'url' || inputType === 'text') {
        // Use unified approach: try LLM synthesis if it's a question, else news ingestion
        if (text.match(/^https?:\/\//)) {
          // URL → unified pipeline
          const fd = new FormData()
          fd.append('topic', text)
          fd.append('include_news_api', 'true')
          fd.append('include_llm_knowledge', 'true')
          fd.append('output_format', 'json')
          const res = await runUnifiedPipeline(fd)
          responseData = res.data
        } else if (text.match(/^(what|who|how|why|when|is|are|tell|explain|summarize|analyze)/i)) {
          // Question → LLM RAG
          const res = await queryLLM(text)
          responseData = res.data
          msgType = 'llm'
        } else {
          // Keyword → news ingestion + LLM
          const [newsRes, llmRes] = await Promise.allSettled([
            queryNews(text),
            queryLLM(`What is the recent news about ${text}?`)
          ])
          const newsData = newsRes.status === 'fulfilled' ? newsRes.value.data : {}
          const llmData = llmRes.status === 'fulfilled' ? llmRes.value.data : {}
          responseData = {
            ...llmData,
            articles: newsData.articles || [],
            collected_count: newsData.collected_count,
          }
        }
      }

      addMessage({
        id: uid(),
        role: 'assistant',
        type: msgType,
        content: responseData.answer || responseData.news_analysis || '',
        data: responseData,
      })
    } catch (err) {
      const errMsg = err?.response?.data?.detail || err.message || 'Request failed'
      addMessage({
        id: uid(),
        role: 'assistant',
        type: 'error',
        content: `⚠️ Error: ${errMsg}`,
      })
    } finally {
      setIsLoading(false)
    }
  }, [])

  const handleNewChat = () => {
    setMessages([])
    setActiveChat(null)
  }

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Background orbs */}
      <div className="orb-1" />
      <div className="orb-2" />
      <div className="orb-3" />

      {/* Mobile sidebar overlay */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 z-20 lg:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <AnimatePresence>
        {(sidebarOpen) && (
          <motion.div
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed left-0 top-0 bottom-0 w-[280px] z-30 lg:hidden"
          >
            <Sidebar
              activeChat={activeChat}
              onSelectChat={id => { setActiveChat(id); setSidebarOpen(false) }}
              onNewChat={() => { handleNewChat(); setSidebarOpen(false) }}
            />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Desktop Sidebar */}
      <div className="hidden lg:flex w-[280px] flex-shrink-0 relative z-10">
        <Sidebar
          activeChat={activeChat}
          onSelectChat={setActiveChat}
          onNewChat={handleNewChat}
        />
      </div>

      {/* Main chat area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">
        {/* Mobile header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-white/[0.06] lg:hidden">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 rounded-lg hover:bg-white/[0.05] text-muted"
          >
            <Menu size={18} />
          </button>
          <span className="font-semibold text-slate-300 text-sm">AetherNews</span>
        </div>

        {/* Chat window */}
        <div className="flex-1 flex flex-col min-h-0">
          <ChatWindow messages={messages} isLoading={isLoading} />
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </div>
  )
}
