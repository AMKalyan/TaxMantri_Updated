const INR = (v) =>
  v == null || isNaN(v)
    ? '₹0'
    : '₹' + Number(v).toLocaleString('en-IN')

const SECTIONS = [
  {
    title: 'Income',
    fields: [
      { key: 'basic_salary', label: 'Basic Salary' },
      { key: 'hra_received', label: 'HRA Received' },
      { key: 'lta', label: 'LTA' },
      { key: 'special_allowance', label: 'Special Allowance' },
      { key: 'other_allowances', label: 'Other Allowances' },
      { key: 'professional_tax', label: 'Professional Tax' },
      { key: 'other_income', label: 'Other Income' },
    ],
  },
  {
    title: 'Deductions',
    fields: [
      { key: 'investments_80c', label: '80C Investments' },
      { key: 'health_insurance_self', label: '80D Self & Family' },
      { key: 'health_insurance_parents', label: '80D Parents' },
      { key: 'employee_nps_80ccd1b', label: 'NPS 80CCD(1B)' },
      { key: 'employer_nps_80ccd2', label: 'NPS 80CCD(2)' },
      { key: 'home_loan_interest', label: 'Home Loan Interest' },
      { key: 'savings_interest_80tta', label: 'Savings Interest' },
    ],
  },
  {
    title: 'Housing',
    fields: [
      { key: 'monthly_rent_paid', label: 'Monthly Rent' },
    ],
  },
]

/**
 * Step 5 — Read-only review of all entered values.
 * Props:
 *   values — all form values from getValues()
 */
export default function Step5Review({ values }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Review Your Details</h2>
        <p className="mt-1 text-sm text-muted">
          Check everything below before we calculate your tax. Go back to any step to make changes.
        </p>
      </div>

      {SECTIONS.map((section) => {
        const filledFields = section.fields.filter(
          (f) => values?.[f.key] != null && Number(values[f.key]) !== 0,
        )
        if (filledFields.length === 0) return null

        return (
          <div key={section.title} className="overflow-hidden rounded-xl border border-line bg-white">
            <div className="border-b border-line bg-surface px-4 py-2.5">
              <span className="text-xs font-semibold uppercase tracking-wide text-subtle">
                {section.title}
              </span>
            </div>
            <div className="divide-y divide-line">
              {filledFields.map((f) => (
                <div key={f.key} className="flex items-center justify-between gap-4 px-4 py-3">
                  <span className="text-sm text-muted">{f.label}</span>
                  <span className="tabular text-right text-sm font-semibold text-ink">
                    {f.key === 'monthly_rent_paid'
                      ? `${INR(values[f.key])}/mo`
                      : INR(values[f.key])}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )
      })}

      {/* Profile metadata */}
      <div className="overflow-hidden rounded-xl border border-line bg-white">
        <div className="border-b border-line bg-surface px-4 py-2.5">
          <span className="text-xs font-semibold uppercase tracking-wide text-subtle">Profile</span>
        </div>
        <div className="divide-y divide-line">
          <div className="flex items-center justify-between gap-4 px-4 py-3">
            <span className="text-sm text-muted">City Type</span>
            <span className="text-right text-sm font-semibold text-ink">
              {values?.city_type === 'metro' ? 'Metro' : 'Non-Metro'}
            </span>
          </div>
          <div className="flex items-center justify-between gap-4 px-4 py-3">
            <span className="text-sm text-muted">Age Bracket</span>
            <span className="text-right text-sm font-semibold text-ink">
              {values?.age_bracket === 'under60' ? 'Under 60'
                : values?.age_bracket === '60_79' ? '60–79 (Senior)'
                : '80+ (Super Senior)'}
            </span>
          </div>
          {values?.parent_senior_citizen && (
            <div className="flex items-center justify-between gap-4 px-4 py-3">
              <span className="text-sm text-muted">Parent Status</span>
              <span className="text-right text-sm font-semibold text-ink">Senior Citizen</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
