import { TrendingDown, Minus } from 'lucide-react'
import { Card, formatINR } from '../ui'

/**
 * Props:
 *   taxResult — full TaxResult from backend
 */
export default function SavingsBanner({ taxResult }) {
  if (!taxResult) return null

  const { recommended_regime, savings_amount } = taxResult
  const savings = Number(savings_amount ?? 0)

  if (savings === 0) {
    return (
      <Card className="flex items-center gap-4 p-5">
        <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-surface text-muted">
          <Minus className="h-5 w-5" />
        </span>
        <p className="font-semibold text-ink">Both regimes result in the same tax.</p>
      </Card>
    )
  }

  const regimeLabel = recommended_regime === 'old' ? 'Old Regime' : 'New Regime'

  return (
    <Card className="flex flex-col gap-4 border-brand-200 bg-brand-50 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
      <div className="flex items-center gap-4">
        <span className="inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
          <TrendingDown className="h-5 w-5" />
        </span>
        <div>
          <p className="text-sm font-medium text-brand-800">Recommended</p>
          <p className="text-lg font-bold text-ink">{regimeLabel}</p>
        </div>
      </div>
      <div className="sm:text-right">
        <p className="text-sm font-medium text-brand-800">You save</p>
        <p className="tabular text-2xl font-extrabold text-brand-700 sm:text-3xl">{formatINR(Math.abs(savings))}</p>
      </div>
    </Card>
  )
}
