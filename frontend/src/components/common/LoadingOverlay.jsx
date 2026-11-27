import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { FileSearch, Calculator, Database, LineChart, Check } from 'lucide-react'

const STEPS = [
  { label: 'Data reading', icon: FileSearch, duration: 1500 },
  { label: 'TAX Calculation', icon: Calculator, duration: 1500 },
  { label: 'RAG Retrieval', icon: Database, duration: 2500 },
  { label: 'Comparative Analysis', icon: LineChart, duration: 1500 },
]

// Full-screen step overlay; calls onComplete after the last step.
export default function LoadingOverlay({ visible, onComplete }) {
  const [stepIndex, setStepIndex] = useState(0)

  useEffect(() => {
    if (!visible) {
      setStepIndex(0)
      return
    }

    let idx = 0
    let timer = null
    const advance = () => {
      if (idx >= STEPS.length - 1) {
        // All steps done — wait a beat then call onComplete
        timer = setTimeout(() => onComplete?.(), 600)
        return
      }
      idx += 1
      setStepIndex(idx)
      timer = setTimeout(advance, STEPS[idx].duration)
    }

    timer = setTimeout(advance, STEPS[0].duration)
    return () => clearTimeout(timer)
  }, [visible, onComplete])

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          role="status"
          aria-live="polite"
          // z-[100] keeps it above the navbar and chat launcher
          className="fixed inset-0 z-[100] flex items-center justify-center bg-white/95 px-4 backdrop-blur-sm"
        >
          <div className="w-full max-w-sm">
            <div className="mb-8 text-center">
              <span className="mx-auto mb-5 block h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
              <h2 className="text-xl font-semibold tracking-tight text-ink sm:text-2xl">Calculating your tax</h2>
              <p className="mt-1 text-sm text-muted">This takes a few seconds.</p>
            </div>

            <div className="mb-5 h-1.5 overflow-hidden rounded-full bg-surface ring-1 ring-inset ring-line">
              <motion.div
                className="h-full rounded-full bg-brand-600"
                initial={{ width: '0%' }}
                animate={{ width: `${((stepIndex + 1) / STEPS.length) * 100}%` }}
                transition={{ duration: 0.6, ease: 'easeOut' }}
              />
            </div>

            <ol className="space-y-2">
              {STEPS.map((step, i) => {
                const isActive = i === stepIndex
                const isPast = i < stepIndex
                const Icon = step.icon

                return (
                  <li
                    key={i}
                    className={`flex items-center gap-3 rounded-xl border px-4 py-3 transition-colors duration-500 ${
                      isActive ? 'border-brand-200 bg-brand-50' : 'border-line bg-white'
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${
                        isPast ? 'bg-brand-600 text-white' : isActive ? 'bg-white text-brand-700 ring-1 ring-brand-200' : 'bg-surface text-subtle'
                      }`}
                    >
                      {isPast ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                    </span>
                    <span className={`flex-1 text-sm font-medium ${isActive || isPast ? 'text-ink' : 'text-subtle'}`}>
                      {step.label}
                    </span>
                    <span className={`text-xs font-medium ${isPast ? 'text-brand-700' : isActive ? 'text-brand-700' : 'text-subtle'}`}>
                      {isPast ? 'Done' : isActive ? 'Working…' : 'Waiting'}
                    </span>
                  </li>
                )
              })}
            </ol>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
