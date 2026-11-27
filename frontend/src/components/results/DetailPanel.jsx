import { motion } from 'framer-motion'
import { X, Lightbulb } from 'lucide-react'
import { formatINR } from '../ui'

const DEDUCTION_LABELS = {
  standard_deduction: 'Standard Deduction',
  hra_exemption: 'HRA Exemption',
  section_80c: '80C Investments',
  section_80d: '80D Health Insurance (self + parents)',
  section_80ccd1b: 'NPS 80CCD(1B)',
  section_80ccd2: 'Employer NPS 80CCD(2)',
  section_24b: 'Home Loan Interest 24(b)',
  section_80tta_ttb: 'Savings Interest 80TTA/TTB',
  professional_tax: 'Professional Tax',
}

/**
 * Props:
 *   regime    ('old' | 'new')
 *   data      — regime breakdown from TaxResult
 *   taxResult — full TaxResult (for suggestions)
 *   side      ('left' | 'right') — animation direction
 *   onClose   (fn)
 */
export default function DetailPanel({ regime, data, taxResult, side, onClose }) {
  if (!data) return null

  const label = regime === 'old' ? 'Old Regime' : 'New Regime'
  const suggestions = regime === 'old'
    ? (taxResult?.old_regime_suggestions ?? taxResult?.optimization_suggestions ?? [])
    : (taxResult?.new_regime_suggestions ?? [])

  const breakdown = data.deduction_breakdown ?? {}
  const filledDeductions = Object.entries(breakdown).filter(([, v]) => Number(v) > 0)

  return (
    <motion.div
      initial={{ opacity: 0, x: side === 'left' ? -24 : 24 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: side === 'left' ? -24 : 24 }}
      transition={{ duration: 0.25, ease: 'easeOut' }}
      className="flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-lift"
    >
      {/* Header */}
      <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div className="min-w-0">
          <h3 className="text-lg font-bold text-ink">{label} — Full Breakdown</h3>
          <p className="tabular mt-0.5 text-sm text-muted">Total Tax: {formatINR(data.total_tax)}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close breakdown"
          className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-muted transition-colors hover:bg-surface hover:text-ink"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      <div className="scrollbar-thin flex-1 space-y-6 overflow-y-auto p-5">
        {/* Income summary */}
        <section>
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Income Summary</h4>
          <div className="space-y-1">
            {[
              { label: 'Gross Income', value: data.gross_income },
              { label: 'Total Deductions', value: data.total_deductions, negative: true },
              { label: 'Taxable Income', value: data.taxable_income, bold: true },
              { label: 'Tax Before Cess', value: data.tax_before_cess },
              { label: '4% Health & Education Cess', value: data.cess },
              { label: 'Total Tax Payable', value: data.total_tax, bold: true, highlight: true },
            ].map((row, i) => (
              <div
                key={i}
                className={[
                  'flex items-center justify-between gap-3 rounded-xl px-3 py-2 text-sm',
                  row.highlight ? 'bg-brand-50 ring-1 ring-inset ring-brand-200' : '',
                ].join(' ')}
              >
                <span className={row.bold ? 'font-semibold text-ink' : 'text-muted'}>{row.label}</span>
                <span className={[
                  'tabular whitespace-nowrap',
                  row.bold ? 'font-bold' : 'font-medium',
                  row.highlight ? 'text-brand-700' : row.negative ? 'text-brand-700' : 'text-ink',
                ].join(' ')}>
                  {row.negative ? `−${formatINR(row.value)}` : formatINR(row.value)}
                </span>
              </div>
            ))}
          </div>
        </section>

        {/* Deduction breakdown */}
        {filledDeductions.length > 0 && (
          <section>
            <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">Deduction Breakdown</h4>
            <div className="overflow-hidden rounded-xl border border-line">
              {filledDeductions.map(([key, value], i) => (
                <div
                  key={key}
                  className={[
                    'flex items-center justify-between gap-3 px-4 py-2.5 text-sm odd:bg-surface',
                    i > 0 ? 'border-t border-line' : '',
                  ].join(' ')}
                >
                  <span className="text-muted">{DEDUCTION_LABELS[key] ?? key}</span>
                  <span className="tabular whitespace-nowrap font-semibold text-brand-700">−{formatINR(value)}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Optimisation suggestions */}
        {suggestions.length > 0 && (
          <section>
            <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-subtle">
              <Lightbulb className="h-3.5 w-3.5 text-amber-600" />
              Optimisation Tips
            </h4>
            <div className="space-y-2">
              {suggestions.map((tip, i) => (
                <div key={i} className="flex gap-2.5 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <span className="shrink-0 text-sm font-bold text-amber-800">{i + 1}.</span>
                  <p className="text-sm leading-relaxed text-ink">{tip}</p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </motion.div>
  )
}
