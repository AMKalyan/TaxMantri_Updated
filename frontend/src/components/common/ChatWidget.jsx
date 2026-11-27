// Floating assistant chat: streams from /api/assistant, session id kept in localStorage.
import { useState, useRef, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageCircle, X, Send, BookOpen, Loader2 } from 'lucide-react'
import { askAssistant } from '../../api/endpoints.js'
import { Badge } from '../ui/index.jsx'

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Returns or creates a stable UUID for this browser session */
function getSessionId() {
    let id = localStorage.getItem('taxmantri_chat_session')
    if (!id) {
        id = crypto.randomUUID()
        localStorage.setItem('taxmantri_chat_session', id)
    }
    return id
}

/** Answers are meant to be plain sentences; strip any stray markdown the model adds. */
function plainText(text = '') {
    return text
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/^\s*[-*]\s+/gm, '• ')
        .trim()
}

// ── Sub-components ────────────────────────────────────────────────────────────

function TypingDots() {
    return (
        <span className="flex items-center gap-1" aria-hidden="true">
            {[0, 1, 2].map(i => (
                <span
                    key={i}
                    className="h-1.5 w-1.5 animate-bounce rounded-full bg-subtle"
                    style={{ animationDelay: `${i * 0.15}s` }}
                />
            ))}
        </span>
    )
}

function MessageBubble({ msg }) {
    const isUser = msg.role === 'user'

    return (
        <div className={`flex flex-col ${isUser ? 'items-end' : 'items-start'}`}>
            <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[15px] leading-relaxed ${
                    isUser
                        ? 'rounded-br-md bg-brand-600 text-white'
                        : 'rounded-bl-md border border-line bg-surface text-ink'
                }`}
            >
                {msg.loading ? (
                    <span className="flex items-center gap-2 py-1">
                        <TypingDots />
                        {msg.step && <span className="text-xs text-subtle">{msg.step}</span>}
                    </span>
                ) : (
                    <span className="whitespace-pre-line break-words">{msg.text}</span>
                )}
            </div>

            {!isUser && msg.grounded === false && (
                <p className="mt-1.5 max-w-[85%] text-xs text-amber-700">
                    Some figures couldn't be verified against the tax engine — double-check before relying on them.
                </p>
            )}

            {!isUser && msg.citations?.length > 0 && (
                <div className="mt-1.5 flex max-w-[85%] flex-wrap gap-1.5">
                    {msg.citations.map((c, i) => {
                        // API returns {section, excerpt} objects
                        const label = typeof c === 'string' ? c : (c?.section || `Ref ${i + 1}`)
                        const tip = typeof c === 'object' ? (c?.excerpt || '') : ''
                        return (
                            <span key={i} title={tip}>
                                <Badge tone="neutral" className="font-medium">
                                    <BookOpen className="h-3 w-3" />
                                    {label}
                                </Badge>
                            </span>
                        )
                    })}
                </div>
            )}
        </div>
    )
}

// ── Welcome message ───────────────────────────────────────────────────────────
const WELCOME = {
    id: '__welcome__',
    role: 'bot',
    text: "Hi! I'm TaxMantri's assistant for AY 2026-27. Ask about deductions, HRA, ITR-1 — or give me your salary and I'll compare regimes and run what-ifs using an exact tax engine.",
    citations: [],
    confidence: null,
}

// Sample questions shown when chat is empty
const SAMPLE_QUESTIONS = [
    'I earn ₹15 lakh. Which regime is better for me?',
    'What if I invest ₹50,000 more in NPS?',
    'How is HRA exemption calculated?',
    'Can I use ITR-1 if I have two houses?',
]

// ── Main Widget ───────────────────────────────────────────────────────────────

// Mounted once at app root; optional profileId personalises answers.
export default function ChatWidget({ profileId: propProfileId = null }) {
    const [open, setOpen] = useState(false)
    const [messages, setMessages] = useState([WELCOME])
    const [input, setInput] = useState('')
    const [loading, setLoading] = useState(false)
    const sessionId = useRef(getSessionId())
    const bottomRef = useRef(null)
    const inputRef = useRef(null)

    // Use prop if given, otherwise read the profileId the ResultsPage saved to localStorage.
    // This lets the backend personalise answers with the user's own salary/deductions/regime.
    const profileId = propProfileId || localStorage.getItem('taxmantri_profile_id')

    // Auto-scroll to bottom on new message
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    // Focus input when widget opens
    useEffect(() => {
        if (open) setTimeout(() => inputRef.current?.focus(), 200)
    }, [open])

    const sendMessage = useCallback(async (question) => {
        if (!question.trim() || loading) return

        const userMsg = { id: Date.now(), role: 'user', text: question }
        const botPlaceholder = { id: Date.now() + 1, role: 'bot', text: '', loading: true }

        setMessages(prev => [...prev, userMsg, botPlaceholder])
        setInput('')
        setLoading(true)

        try {
            const onStep = (label) => setMessages(prev => prev.map(m =>
                m.id === botPlaceholder.id ? { ...m, step: label } : m
            ))
            const data = await askAssistant(question, sessionId.current, profileId, onStep)
            setMessages(prev => prev.map(m =>
                m.id === botPlaceholder.id
                    ? {
                        ...m,
                        loading: false,
                        text: plainText(data.answer) || 'No answer returned.',
                        citations: data.citations || [],
                        grounded: data.grounded,
                    }
                    : m
            ))
        } catch (err) {
            const isUnavailable = err?.response?.status === 503 || err?.status === 503
            const httpMessage = err?.kind === 'http' ? err.message : null
            setMessages(prev => prev.map(m =>
                m.id === botPlaceholder.id
                    ? {
                        ...m,
                        loading: false,
                        text: isUnavailable
                            ? 'The assistant is unavailable right now. Please try again later.'
                            : httpMessage || 'Could not reach the server — it may be waking up. Please try again in a moment.',
                        citations: [],
                    }
                    : m
            ))
        } finally {
            setLoading(false)
        }
    }, [loading, profileId])

    const handleSubmit = (e) => {
        e.preventDefault()
        sendMessage(input)
    }

    const unreadCount = messages.filter(m => m.role === 'bot' && m.id !== '__welcome__').length

    return (
        <>
            <AnimatePresence>
                {open && (
                    <motion.div
                        key="chat-panel"
                        role="dialog"
                        aria-label="TaxMantri assistant"
                        initial={{ opacity: 0, y: 16 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: 16 }}
                        transition={{ duration: 0.2, ease: 'easeOut' }}
                        className="fixed inset-0 z-[60] flex flex-col overflow-hidden bg-white sm:inset-auto sm:bottom-24 sm:right-4 sm:h-[560px] sm:max-h-[calc(100vh-8rem)] sm:w-[380px] sm:rounded-2xl sm:border sm:border-line sm:shadow-lift"
                    >
                        {/* Header */}
                        <div className="flex flex-shrink-0 items-center gap-3 border-b border-line px-4 py-3">
                            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                                <MessageCircle className="h-5 w-5" />
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-sm font-semibold leading-tight text-ink">TaxMantri assistant</p>
                                <p className="truncate text-xs text-subtle">Powered by Gemini · Income Tax Act 1961</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => setOpen(false)}
                                aria-label="Close chat"
                                className="-mr-1 flex h-11 w-11 items-center justify-center rounded-xl text-muted transition-colors hover:bg-surface hover:text-ink"
                            >
                                <X className="h-5 w-5" />
                            </button>
                        </div>

                        {/* Messages */}
                        <div className="flex-1 space-y-3 overflow-y-auto px-4 py-4">
                            {messages.map(msg => (
                                <MessageBubble key={msg.id} msg={msg} />
                            ))}

                            {/* Starter questions while only the welcome message exists */}
                            {messages.length === 1 && (
                                <div className="flex flex-col items-start gap-2 pt-1">
                                    {SAMPLE_QUESTIONS.map((q, i) => (
                                        <button
                                            key={i}
                                            type="button"
                                            onClick={() => sendMessage(q)}
                                            className="min-h-[44px] max-w-full rounded-xl border border-line bg-white px-3.5 py-2 text-left text-sm font-medium text-ink transition-colors hover:border-brand-200 hover:bg-brand-50 hover:text-brand-800"
                                        >
                                            {q}
                                        </button>
                                    ))}
                                </div>
                            )}
                            <div ref={bottomRef} />
                        </div>

                        {/* Input */}
                        <form
                            onSubmit={handleSubmit}
                            className="flex flex-shrink-0 items-center gap-2 border-t border-line bg-white px-3 py-3"
                        >
                            <input
                                ref={inputRef}
                                type="text"
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                placeholder="Ask a tax question…"
                                aria-label="Your question"
                                disabled={loading}
                                className="min-h-[44px] min-w-0 flex-1 rounded-xl border border-line bg-white px-3.5 text-[15px] text-ink outline-none transition placeholder:text-subtle focus:border-brand-500 focus:ring-2 focus:ring-brand-100 disabled:bg-surface disabled:opacity-60"
                            />
                            <button
                                type="submit"
                                disabled={!input.trim() || loading}
                                aria-label="Send"
                                className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
                            >
                                {loading
                                    ? <Loader2 className="h-4 w-4 animate-spin" />
                                    : <Send className="h-4 w-4" />
                                }
                            </button>
                        </form>
                    </motion.div>
                )}
            </AnimatePresence>

            {/* Launcher; hidden on mobile while the full-screen panel is open */}
            <motion.button
                type="button"
                onClick={() => setOpen(v => !v)}
                whileTap={{ scale: 0.95 }}
                className={`fixed bottom-4 right-4 z-50 h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lift transition-colors hover:bg-brand-700 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 ${open ? 'hidden sm:flex' : 'flex'}`}
                aria-label={open ? 'Close tax assistant' : 'Open tax assistant'}
                aria-expanded={open}
            >
                {open ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}

                {/* Unread dot when closed and there are replies */}
                {!open && unreadCount > 0 && (
                    <span className="absolute right-0.5 top-0.5 h-3.5 w-3.5 rounded-full border-2 border-white bg-red-500" />
                )}
            </motion.button>
        </>
    )
}
