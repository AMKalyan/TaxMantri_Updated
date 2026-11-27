import { motion } from 'framer-motion'
import { CheckCircle, ChevronDown } from 'lucide-react'
import { Badge, formatINR } from '../ui'

/**
 * Single regime summary card.
 *
 * Props:
 *   regime        ('old' | 'new')
 *   data          — regime breakdown object from TaxResult
 *   isRecommended (bool)
 *   isExpanded    (bool)
 *   onClick       (fn)
 */
export default function RegimeCard({ regime, data, isRecommended, isExpanded, onClick }) {
  if (!data) return null

  const label = regime === 'old' ? 'Old Regime' : 'New Regime'
  const subtitle = regime === 'old' ? 'With deductions (80C, HRA, etc.)' : 'Simplified slabs (115BAC)'

  return (
    <motion.div
      layout
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-expanded={isExpanded}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick?.()
        }
      }}
      className={[
        'relative cursor-pointer rounded-2xl bg-white shadow-card transition-shadow hover:shadow-lift',
        'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
        isRecommended ? 'border-2 border-brand-600' : 'border border-line',
        isExpanded && !isRecommended ? 'ring-2 ring-slate-300' : '',
      ].join(' ')}
    >
      <div className="p-5 sm:p-6">
        {/* Header */}
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h3 className="text-lg font-bold text-ink">{label}</h3>
              {isRecommended && (
                <Badge tone="brand">
                  <CheckCircle className="h-3.5 w-3.5" />
                  Recommended
                </Badge>
              )}
            </div>
            <p className="mt-1 text-sm text-muted">{subtitle}</p>
          </div>
          <ChevronDown
            className={[
              'mt-1 h-5 w-5 shrink-0 text-subtle transition-transform',
              isExpanded ? 'rotate-180' : '',
            ].join(' ')}
          />
        </div>

        {/* Total tax */}
        <div className="mb-5">
          <p className="text-xs font-medium uppercase tracking-wide text-subtle">Total tax payable</p>
          <p className={[
            'tabular mt-1 text-3xl font-extrabold tracking-tight sm:text-4xl',
            isRecommended ? 'text-brand-700' : 'text-ink',
          ].join(' ')}>
            {formatINR(data.total_tax)}
          </p>
          {data.cess > 0 && (
            <p className="tabular mt-1 text-xs text-subtle">incl. {formatINR(data.cess)} cess</p>
          )}
        </div>

        {/* Key stats */}
        <dl className="space-y-2.5 text-sm">
          <div className="flex justify-between gap-3">
            <dt className="text-muted">Gross Income</dt>
            <dd className="tabular font-semibold text-ink">{formatINR(data.gross_income)}</dd>
          </div>
          <div className="flex justify-between gap-3">
            <dt className="text-muted">Total Deductions</dt>
            <dd className="tabular font-semibold text-ink">{formatINR(data.total_deductions)}</dd>
          </div>
          <div className="flex justify-between gap-3 border-t border-line pt-2.5">
            <dt className="font-semibold text-ink">Taxable Income</dt>
            <dd className="tabular font-bold text-ink">{formatINR(data.taxable_income)}</dd>
          </div>
        </dl>

        <p className="mt-5 text-center text-sm font-medium text-brand-700">
          {isExpanded ? 'Tap to close breakdown' : 'Tap to see full breakdown'}
        </p>
      </div>
    </motion.div>
  )
}
