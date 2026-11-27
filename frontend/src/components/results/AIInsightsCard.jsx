import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Sparkles, ChevronDown, ChevronUp, BookOpen, Scale, TrendingDown } from 'lucide-react'
import { Badge, Card, formatINR } from '../ui'

const INR = (v) => formatINR(Math.abs(Number(v ?? 0)))

// Maps DeductionBreakdown field keys → human label + IT Act section
const SECTION_MAP = {
  standard_deduction: { label: 'Standard Deduction', section: 'Sec 16(ia)' },
  hra_exemption: { label: 'HRA Exemption', section: 'Rule 2A' },
  section_80c: { label: '80C Investments', section: 'Sec 80C' },
  section_80d: { label: 'Health Insurance', section: 'Sec 80D' },
  section_80ccd1b: { label: 'NPS (Employee)', section: 'Sec 80CCD(1B)' },
  section_80ccd2: { label: 'NPS (Employer)', section: 'Sec 80CCD(2)' },
  section_80tta_ttb: { label: 'Savings Interest', section: 'Sec 80TTA/TTB' },
  section_24b: { label: 'Home Loan Interest', section: 'Sec 24(b)' },
  professional_tax: { label: 'Professional Tax', section: 'Sec 16(iii)' },
}

function SectionLabel({ icon: Icon, children }) {
  return (
    <div className="mb-2.5 flex items-center gap-1.5">
      {Icon && <Icon className="h-3.5 w-3.5 text-subtle" />}
      <span className="text-xs font-semibold uppercase tracking-wide text-subtle">{children}</span>
    </div>
  )
}

// Calculation flow steps
function CalcFlow({ regime }) {
  if (!regime) return null
  const steps = [
    { label: 'Gross Income', value: regime.gross_income },
    { label: 'Deductions', value: regime.total_deductions, minus: true },
    { label: 'Taxable Income', value: regime.taxable_income },
    { label: 'Income Tax', value: regime.tax_before_cess },
    { label: '+ Health Cess', value: regime.cess },
    { label: 'Final Tax', value: regime.total_tax, highlight: true },
  ]

  return (
    <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      {steps.map((s, i) => (
        <div
          key={i}
          className={[
            'rounded-xl px-3 py-2',
            s.highlight ? 'bg-brand-600 text-white' : 'border border-line bg-surface',
          ].join(' ')}
        >
          <p className={`text-xs font-medium ${s.highlight ? 'text-brand-50' : 'text-subtle'}`}>{s.label}</p>
          <p className={`tabular mt-0.5 text-sm font-bold ${s.highlight ? 'text-white' : 'text-ink'}`}>
            {s.minus ? '−' : ''}{INR(s.value)}
          </p>
        </div>
      ))}
    </div>
  )
}

// Deduction breakdown rows — only non-zero
function DeductionTable({ breakdown }) {
  if (!breakdown) return null
  const rows = Object.entries(breakdown)
    .filter(([key, val]) => val > 0 && SECTION_MAP[key])
    .map(([key, val]) => ({ ...SECTION_MAP[key], amount: val }))

  if (rows.length === 0) return null

  return (
    <div className="mb-5">
      <SectionLabel icon={TrendingDown}>Deductions Applied</SectionLabel>
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[420px] text-sm">
          <thead>
            <tr className="border-b border-line bg-surface">
              <th className="px-3 py-2 text-left text-xs font-semibold text-muted">Deduction</th>
              <th className="px-3 py-2 text-left text-xs font-semibold text-muted">IT Act Section</th>
              <th className="px-3 py-2 text-right text-xs font-semibold text-muted">Amount</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="even:bg-surface">
                <td className="px-3 py-2 text-ink">{r.label}</td>
                <td className="px-3 py-2"><Badge tone="neutral">{r.section}</Badge></td>
                <td className="tabular whitespace-nowrap px-3 py-2 text-right font-semibold text-brand-700">
                  {INR(r.amount)}
                </td>
              </tr>
            ))}
            <tr className="border-t border-line bg-white">
              <td className="px-3 py-2 font-semibold text-ink" colSpan={2}>Total Deductions</td>
              <td className="tabular whitespace-nowrap px-3 py-2 text-right font-bold text-ink">
                {INR(rows.reduce((s, r) => s + r.amount, 0))}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

/**
 * AIInsightsCard — LLM rationale + IT Act citations + calculation summary.
 * Props:
 *   taxResult — full TaxResult from backend
 */
export default function AIInsightsCard({ taxResult }) {
  const [lawExpanded, setLawExpanded] = useState(false)

  if (!taxResult) return null

  const { rationale, citations = [], law_context = '', recommended_regime, old_regime, new_regime } = taxResult

  const recRegime = recommended_regime === 'old' ? old_regime : new_regime
  const breakdown = recRegime?.deduction_breakdown
  const regimeLabel = recommended_regime === 'old' ? 'Old Regime' : 'New Regime'

  const hasContent = rationale || citations.length > 0 || law_context || recRegime
  if (!hasContent) return null

  return (
    <Card className="p-5 sm:p-6">
      {/* Header */}
      <div className="mb-4 flex items-start gap-3">
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
          <Sparkles className="h-5 w-5" />
        </span>
        <div className="min-w-0">
          <h2 className="font-bold text-ink">AI Tax Insights</h2>
          <p className="text-xs text-subtle">
            Explained by Gemini · Grounded in Income Tax Act · {regimeLabel} breakdown
          </p>
        </div>
      </div>

      {/* Rationale */}
      {rationale && <p className="mb-5 text-sm leading-relaxed text-ink">{rationale}</p>}

      <div className="my-4 border-t border-line" />

      {/* Calculation flow */}
      {recRegime && (
        <>
          <SectionLabel>{regimeLabel} — Calculation Breakdown</SectionLabel>
          <CalcFlow regime={recRegime} />
        </>
      )}

      <DeductionTable breakdown={breakdown} />

      {/* Citation chips */}
      {citations.length > 0 && (
        <div className="mb-5">
          <SectionLabel icon={Scale}>Referenced IT Act Sections</SectionLabel>
          <div className="flex flex-wrap gap-2">
            {citations.map((c, i) => (
              <span key={i} title={c.excerpt || ''}>
                <Badge tone="neutral">{c.section || `Section ${i + 1}`}</Badge>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Collapsible law context */}
      {law_context && (
        <div className="border-t border-line pt-2">
          <button
            type="button"
            onClick={() => setLawExpanded(v => !v)}
            aria-expanded={lawExpanded}
            className="flex min-h-[44px] w-full items-center gap-2 text-left text-sm font-semibold text-brand-700 transition-colors hover:text-brand-800"
          >
            <BookOpen className="h-4 w-4" />
            <span>View Full Legal Context</span>
            {lawExpanded
              ? <ChevronUp className="ml-auto h-4 w-4" />
              : <ChevronDown className="ml-auto h-4 w-4" />
            }
          </button>

          <AnimatePresence>
            {lawExpanded && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25 }}
                className="overflow-hidden"
              >
                <p className="mt-2 whitespace-pre-line rounded-xl border border-line bg-surface p-4 text-xs leading-relaxed text-muted">
                  {law_context}
                </p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </Card>
  )
}
