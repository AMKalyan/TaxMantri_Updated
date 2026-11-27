import CurrencyInput from '../../common/CurrencyInput.jsx'

const AGE_OPTIONS = [
  { value: 'under60', label: 'Under 60', desc: 'Standard tax slabs & limits' },
  { value: '60_79', label: '60–79', desc: 'Senior citizen — higher 80D limits' },
  { value: '80plus', label: '80+', desc: 'Super senior — no tax up to ₹5L (old)' },
]

/**
 * Step 4 — Other details (age bracket, other income).
 */
export default function Step4Other({ register, errors }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Other Details</h2>
        <p className="mt-1 text-sm text-muted">
          Age bracket affects tax slabs and deduction limits.
        </p>
      </div>

      <fieldset className="space-y-2">
        <legend className="mb-1.5 text-sm font-medium text-ink">
          Age Bracket <span className="text-red-600">*</span>
        </legend>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {AGE_OPTIONS.map((opt) => (
            <label key={opt.value} className="relative block cursor-pointer">
              <input
                type="radio"
                value={opt.value}
                className="sr-only peer"
                {...register('age_bracket')}
              />
              <div className={[
                'h-full min-h-[44px] rounded-xl border bg-white p-4 transition-colors hover:border-slate-300 sm:text-center',
                'peer-checked:border-brand-600 peer-checked:bg-brand-50 peer-checked:ring-1 peer-checked:ring-brand-600',
                'peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500',
                errors.age_bracket ? 'border-red-500' : 'border-line',
              ].join(' ')}>
                <div className="text-sm font-semibold text-ink">{opt.label}</div>
                <div className="mt-0.5 text-xs leading-snug text-subtle">{opt.desc}</div>
              </div>
            </label>
          ))}
        </div>
        {errors.age_bracket && (
          <p className="text-xs font-medium text-red-600">{errors.age_bracket.message}</p>
        )}
      </fieldset>

      <CurrencyInput
        label="Other Income (Annual)"
        error={errors.other_income?.message}
        helpText="Interest from savings and FDs, and other non-salary income. Business or freelance income needs ITR-3/4."
        {...register('other_income', { valueAsNumber: true })}
      />
    </div>
  )
}
