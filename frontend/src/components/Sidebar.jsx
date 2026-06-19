import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Newspaper, TrendingUp, Settings,
  Plus, Search, MoreHorizontal, Pencil, Trash2,
  ChevronRight, Zap, X, Check
} from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'

const NAV_ITEMS = [
  { icon: LayoutDashboard, label: 'Dashboard', to: '/dashboard' },
  { icon: Newspaper, label: 'Newsletter', to: '/newsletter' },
  { icon: TrendingUp, label: 'Top 100 News', to: '/top-news' },
  { icon: Settings, label: 'Settings', to: '/settings' },
]

const HISTORY_DATA = {
  Today: [
    { id: 'h1', name: 'Reuters Article Analysis' },
    { id: 'h2', name: 'BBC Election Coverage' },
    { id: 'h3', name: 'AI Industry Report 2025' },
  ],
  Yesterday: [
    { id: 'h4', name: 'Economic Report Analysis' },
    { id: 'h5', name: 'Market Crash Analysis' },
    { id: 'h6', name: 'Climate Policy Deep Dive' },
  ],
  'Last Week': [
    { id: 'h7', name: 'Tech Layoffs Coverage' },
    { id: 'h8', name: 'Federal Reserve Report' },
  ],
}

export default function Sidebar({ activeChat, onSelectChat, onNewChat }) {
  const [search, setSearch] = useState('')
  const [history, setHistory] = useState(HISTORY_DATA)
  const [renamingId, setRenamingId] = useState(null)
  const [renameValue, setRenameValue] = useState('')
  const [hoveredId, setHoveredId] = useState(null)
  const navigate = useNavigate()

  const startRename = (item, e) => {
    e.stopPropagation()
    setRenamingId(item.id)
    setRenameValue(item.name)
  }

  const confirmRename = (groupKey, itemId) => {
    setHistory(prev => ({
      ...prev,
      [groupKey]: prev[groupKey].map(i =>
        i.id === itemId ? { ...i, name: renameValue } : i
      )
    }))
    setRenamingId(null)
  }

  const deleteItem = (groupKey, itemId, e) => {
    e.stopPropagation()
    setHistory(prev => ({
      ...prev,
      [groupKey]: prev[groupKey].filter(i => i.id !== itemId)
    }))
  }

  const filteredHistory = Object.entries(history).reduce((acc, [group, items]) => {
    const filtered = items.filter(i =>
      i.name.toLowerCase().includes(search.toLowerCase())
    )
    if (filtered.length > 0) acc[group] = filtered
    return acc
  }, {})

  return (
    <aside className="flex flex-col h-full w-full bg-surface border-r border-white/5 relative z-10">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg gradient-primary flex items-center justify-center shadow-glow-primary flex-shrink-0">
          <Zap size={16} className="text-white" />
        </div>
        <div>
          <p className="font-display font-700 text-white text-[15px] leading-tight">AetherNews</p>
          <p className="text-[10px] text-muted font-mono tracking-wider uppercase">AI Intelligence</p>
        </div>
      </div>

      {/* New Analysis Button */}
      <div className="px-3 pt-4 pb-2">
        <button
          onClick={onNewChat}
          className="w-full flex items-center gap-2.5 px-4 py-2.5 rounded-[10px] glass-primary text-primary-light text-sm font-semibold transition-all hover:shadow-glow-primary group"
        >
          <Plus size={16} className="group-hover:rotate-90 transition-transform duration-200" />
          New Analysis
        </button>
      </div>

      {/* Search */}
      <div className="px-3 pb-3">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.06]">
          <Search size={13} className="text-muted flex-shrink-0" />
          <input
            type="text"
            placeholder="Search history..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-transparent border-none outline-none text-[13px] text-slate-300 placeholder-muted flex-1 min-w-0"
          />
          {search && (
            <button onClick={() => setSearch('')}>
              <X size={12} className="text-muted hover:text-white" />
            </button>
          )}
        </div>
      </div>

      {/* History */}
      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-4 min-h-0">
        <AnimatePresence>
          {Object.entries(filteredHistory).map(([group, items]) => (
            <motion.div
              key={group}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
            >
              <p className="text-[10px] font-semibold text-muted uppercase tracking-widest px-1 mb-1.5">
                {group}
              </p>
              <div className="space-y-0.5">
                {items.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => onSelectChat?.(item.id)}
                    onMouseEnter={() => setHoveredId(item.id)}
                    onMouseLeave={() => setHoveredId(null)}
                    className={`history-item group ${activeChat === item.id ? 'active' : ''}`}
                  >
                    {renamingId === item.id ? (
                      <div className="flex items-center gap-1.5 flex-1 min-w-0" onClick={e => e.stopPropagation()}>
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={e => setRenameValue(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') confirmRename(group, item.id)
                            if (e.key === 'Escape') setRenamingId(null)
                          }}
                          className="flex-1 min-w-0 bg-white/10 border border-primary/30 rounded px-2 py-0.5 text-xs text-white outline-none"
                        />
                        <button onClick={() => confirmRename(group, item.id)}>
                          <Check size={12} className="text-success" />
                        </button>
                        <button onClick={() => setRenamingId(null)}>
                          <X size={12} className="text-muted" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <span className="text-[13px] text-slate-300 truncate flex-1 min-w-0">
                          {item.name}
                        </span>
                        <div className={`flex items-center gap-1 flex-shrink-0 transition-opacity ${hoveredId === item.id ? 'opacity-100' : 'opacity-0'}`}>
                          <button
                            onClick={e => startRename(item, e)}
                            className="p-1 rounded hover:bg-white/10 text-muted hover:text-white"
                          >
                            <Pencil size={11} />
                          </button>
                          <button
                            onClick={e => deleteItem(group, item.id, e)}
                            className="p-1 rounded hover:bg-danger/20 text-muted hover:text-danger"
                          >
                            <Trash2 size={11} />
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                ))}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {Object.keys(filteredHistory).length === 0 && search && (
          <p className="text-xs text-muted text-center py-6">No results for "{search}"</p>
        )}
      </div>

      {/* Nav Links */}
      <div className="px-3 py-3 border-t border-white/5 space-y-0.5">
        {NAV_ITEMS.map(({ icon: Icon, label, to }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          >
            <Icon size={16} className="flex-shrink-0" />
            {label}
            {label === 'Settings' && (
              <ChevronRight size={13} className="ml-auto text-muted opacity-50" />
            )}
          </NavLink>
        ))}
      </div>
    </aside>
  )
}
