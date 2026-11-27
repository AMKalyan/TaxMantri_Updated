import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import RegimeCard from './RegimeCard.jsx'
import DetailPanel from './DetailPanel.jsx'

/**
 * Regime card grid with expand-to-detail.
 *
 * Mobile:    single column (stacked)
 * md+ default:   two equal columns
 * md+ old open:  card left (280px), detail right
 * md+ new open:  detail left, card right (280px)
 *
 * Props:
 *   taxResult — full TaxResult from backend
 */
export default function RegimeCardPair({ taxResult }) {
  const [expandedRegime, setExpandedRegime] = useState(null)

  if (!taxResult) return null

  const { old_regime, new_regime, recommended_regime } = taxResult

  const toggleRegime = (regime) => {
    setExpandedRegime((prev) => (prev === regime ? null : regime))
  }

  const isOldExpanded = expandedRegime === 'old'
  const isNewExpanded = expandedRegime === 'new'

  const gridClass = isOldExpanded
    ? 'md:grid-cols-regime-left'
    : isNewExpanded
      ? 'md:grid-cols-regime-right'
      : 'md:grid-cols-2'

  return (
    <motion.div
      layout
      className={`grid grid-cols-1 gap-4 ${gridClass}`}
      transition={{ duration: 0.3, ease: 'easeInOut' }}
    >
      {/* Left column: the Old card, or the New breakdown when New is open */}
      {isNewExpanded ? (
        <AnimatePresence mode="sync">
          <DetailPanel
            key="new-detail"
            regime="new"
            data={new_regime}
            taxResult={taxResult}
            side="left"
            onClose={() => setExpandedRegime(null)}
          />
        </AnimatePresence>
      ) : (
        <RegimeCard
          regime="old"
          data={old_regime}
          isRecommended={recommended_regime === 'old'}
          isExpanded={isOldExpanded}
          onClick={() => toggleRegime('old')}
        />
      )}

      {/* Right column: the New card, or the Old breakdown when Old is open */}
      {isOldExpanded ? (
        <AnimatePresence mode="sync">
          <DetailPanel
            key="old-detail"
            regime="old"
            data={old_regime}
            taxResult={taxResult}
            side="right"
            onClose={() => setExpandedRegime(null)}
          />
        </AnimatePresence>
      ) : (
        <RegimeCard
          regime="new"
          data={new_regime}
          isRecommended={recommended_regime === 'new'}
          isExpanded={isNewExpanded}
          onClick={() => toggleRegime('new')}
        />
      )}
    </motion.div>
  )
}
