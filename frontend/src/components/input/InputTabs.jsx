import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, PenLine } from 'lucide-react'
import UploadTab from './UploadTab.jsx'
import ManualWizard from './ManualWizard.jsx'

const TABS = [
  { id: 'upload', label: 'Upload Form 16', icon: <Upload className="hidden h-4 w-4 shrink-0 min-[400px]:block" aria-hidden="true" /> },
  { id: 'manual', label: 'Manual Entry', icon: <PenLine className="hidden h-4 w-4 shrink-0 min-[400px]:block" aria-hidden="true" /> },
]

/**
 * Props:
 *   onCalculationComplete (fn) — passed through to child tabs
 *   onCalculating (fn)         — passed through to child tabs
 */
export default function InputTabs({ onCalculationComplete, onCalculating }) {
  // Default to manual entry tab if the user has form data saved (came back via Edit Details)
  const hasSavedForm = !!localStorage.getItem('taxmantri_last_form')
  const [activeTab, setActiveTab] = useState(hasSavedForm ? 'manual' : 'upload')

  return (
    <div>
      {/* Tab switcher */}
      <div role="group" aria-label="How to add your details" className="mb-8 grid grid-cols-2 gap-1 rounded-xl border border-line bg-surface p-1">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            aria-pressed={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={[
              'flex min-h-[44px] items-center justify-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors',
              'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
              activeTab === tab.id
                ? 'bg-white text-ink shadow-card ring-1 ring-line'
                : 'text-muted hover:text-ink',
            ].join(' ')}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, x: activeTab === 'upload' ? -12 : 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: activeTab === 'upload' ? 12 : -12 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'upload' ? (
            <UploadTab
              onCalculationComplete={onCalculationComplete}
              onCalculating={onCalculating}
            />
          ) : (
            <ManualWizard
              onCalculationComplete={onCalculationComplete}
              onCalculating={onCalculating}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
