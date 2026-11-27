import CurrencyInput from '../../common/CurrencyInput.jsx'

/**
 * Step 3 — Housing (HRA / rent).
 */
export default function Step3Housing({ register, errors }) {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Housing Details</h2>
        <p className="mt-1 text-sm text-muted">
          Used for HRA exemption under Rule 2A. Leave rent at ₹0 if you don't pay rent.
        </p>
      </div>

      <CurrencyInput
        label="Monthly Rent Paid (₹)"
        error={errors.monthly_rent_paid?.message}
        helpText="Enter the amount you pay each month. ₹0 if not paying rent."
        {...register('monthly_rent_paid', { valueAsNumber: true })}
      />

      <fieldset className="space-y-2">
        <legend className="mb-1.5 text-sm font-medium text-ink">
          City Type <span className="text-red-600">*</span>
        </legend>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {[
            { value: 'metro', label: 'Metro', desc: 'Mumbai, Delhi, Chennai, Kolkata (50% of basic)' },
            { value: 'non_metro', label: 'Non-Metro', desc: 'All other cities (40% of basic)' },
          ].map((opt) => (
            <label
              key={opt.value}
              className="relative block cursor-pointer"
            >
              <input
                type="radio"
                value={opt.value}
                className="sr-only peer"
                {...register('city_type')}
              />
              <div className={[
                'min-h-[44px] rounded-xl border bg-white p-4 transition-colors hover:border-slate-300',
                'peer-checked:border-brand-600 peer-checked:bg-brand-50 peer-checked:ring-1 peer-checked:ring-brand-600',
                'peer-focus-visible:ring-2 peer-focus-visible:ring-brand-500',
                errors.city_type ? 'border-red-500' : 'border-line',
              ].join(' ')}>
                <div className="text-sm font-semibold text-ink">{opt.label}</div>
                <div className="mt-0.5 text-xs text-subtle">{opt.desc}</div>
              </div>
            </label>
          ))}
        </div>
        {errors.city_type && (
          <p className="text-xs font-medium text-red-600">{errors.city_type.message}</p>
        )}
      </fieldset>
    </div>
  )
}
