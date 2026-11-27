import { useState } from 'react'
import { Badge } from '../ui'

const FIELD_LABELS = {
  basic_salary: 'Basic Salary (Annual)',
  hra_received: 'HRA Received (Annual)',
  special_allowance: 'Special Allowance (Annual)',
  other_allowances: 'Other Allowances (Annual)',
  professional_tax: 'Professional Tax (Annual)',
  lta: 'Leave Travel Allowance',
  investments_80c: '80C Investments',
  health_insurance_self: '80D — Self & Family',
  health_insurance_parents: '80D — Parents',
  employee_nps_80ccd1b: 'NPS 80CCD(1B)',
  employer_nps_80ccd2: 'Employer NPS 80CCD(2)',
  home_loan_interest: 'Home Loan Interest 24(b)',
  savings_interest_80tta: 'Savings Interest 80TTA',
  other_income: 'Other Income',
}

/**
 * Renders the OCR extraction review grid.
 * Shows successfully extracted fields (green/yellow) as editable inputs; yellow ones
 * (e.g. anything read from a scan) are highlighted for review. Red (not found)
 * fields are hidden — users fill those in the manual wizard.
 *
 * Props:
 *   extractedFields  — { fieldName: { value, confidence } }
 *   onChange (fn)    — called with updated { fieldName: value } dict on each change
 */
export default function OCRFieldReview({ extractedFields, onChange }) {
  const [overrides, setOverrides] = useState({})

  const handleChange = (fieldName, value) => {
    const next = { ...overrides, [fieldName]: value }
    setOverrides(next)
    onChange?.(next)
  }

  if (!extractedFields || Object.keys(extractedFields).length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line bg-surface px-4 py-6 text-center text-sm text-muted">
        No fields were extracted. Please fill them in manually below.
      </p>
    )
  }

  // Only show green and yellow fields (successfully extracted)
  const visibleFields = Object.entries(extractedFields).filter(
    ([, fieldData]) => fieldData.confidence !== 'red'
  )

  if (visibleFields.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-line bg-surface px-4 py-6 text-center text-sm text-muted">
        No fields could be auto-filled. Please fill them in manually below.
      </p>
    )
  }

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {visibleFields.map(([fieldName, fieldData]) => {
          const currentValue = overrides[fieldName] ?? fieldData.value ?? ''
          const label = FIELD_LABELS[fieldName] ?? fieldName

          const needsCheck = fieldData.confidence === 'yellow'

          return (
            <div
              key={fieldName}
              className={`rounded-xl border p-3.5 ${needsCheck ? 'border-amber-300 bg-amber-50' : 'border-line bg-white'}`}
            >
              <div className="mb-2 flex min-h-[24px] items-center justify-between gap-2">
                <label htmlFor={`ocr-${fieldName}`} className="text-xs font-medium text-ink">{label}</label>
                {needsCheck && <Badge tone="warning" className="shrink-0">Please check</Badge>}
              </div>
              <div className="relative">
                <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 select-none text-sm font-medium text-subtle">₹</span>
                <input
                  id={`ocr-${fieldName}`}
                  type="number"
                  inputMode="numeric"
                  min={0}
                  value={currentValue}
                  onChange={(e) => handleChange(fieldName, e.target.value === '' ? '' : Number(e.target.value))}
                  className={`tabular w-full min-h-[44px] rounded-xl border bg-white pl-8 pr-3.5 py-2 text-base text-ink transition-colors focus:outline-none focus:ring-2 sm:text-sm ${needsCheck ? 'border-amber-300 focus:border-amber-500 focus:ring-amber-500/30' : 'border-line hover:border-slate-300 focus:border-brand-600 focus:ring-brand-500/30'}`}
                />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
