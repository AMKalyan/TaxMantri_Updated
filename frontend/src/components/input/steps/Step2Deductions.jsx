import { useWatch } from 'react-hook-form'
import CurrencyInput from '../../common/CurrencyInput.jsx'

/**
 * Step 2 — Deductions (Chapter VI-A).
 */
export default function Step2Deductions({ register, errors, control }) {
  const parentSenior = useWatch({ control, name: 'parent_senior_citizen', defaultValue: false })

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-ink">Deductions</h2>
        <p className="mt-1 text-sm text-muted">
          Chapter VI-A deductions. Leave blank if not applicable.
        </p>
      </div>

      <CurrencyInput
        label="80C Investments (Annual)"
        error={errors.investments_80c?.message}
        helpText="ELSS, PPF, LIC, EPF, NSC, etc. — capped at ₹1,50,000"
        {...register('investments_80c', { valueAsNumber: true })}
      />

      <CurrencyInput
        label="80D — Health Insurance (Self, Spouse & Children)"
        error={errors.health_insurance_self?.message}
        helpText="Self, spouse and children. Cap ₹25,000 (₹50,000 if you are 60+). Old regime only."
        {...register('health_insurance_self', { valueAsNumber: true })}
      />

      <label
        htmlFor="parent_sc"
        className="flex min-h-[44px] cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink"
      >
        <input
          type="checkbox"
          id="parent_sc"
          className="h-4 w-4 shrink-0 rounded accent-brand-600"
          {...register('parent_senior_citizen')}
        />
        My parents are senior citizens (60+)
      </label>

      <CurrencyInput
        label="80D — Health Insurance (Parents)"
        error={errors.health_insurance_parents?.message}
        helpText={`Cap: ${parentSenior ? '₹50,000 (senior)' : '₹25,000'}`}
        {...register('health_insurance_parents', { valueAsNumber: true })}
      />

      <CurrencyInput
        label="NPS — Employee Contribution 80CCD(1B)"
        error={errors.employee_nps_80ccd1b?.message}
        helpText="Additional NPS deduction up to ₹50,000 — old regime only"
        {...register('employee_nps_80ccd1b', { valueAsNumber: true })}
      />

      <CurrencyInput
        label="NPS — Employer Contribution 80CCD(2)"
        error={errors.employer_nps_80ccd2?.message}
        helpText="Up to 14% of basic salary (new regime) or 10% (old regime)."
        {...register('employer_nps_80ccd2', { valueAsNumber: true })}
      />

      <CurrencyInput
        label="Home Loan Interest 24(b)"
        error={errors.home_loan_interest?.message}
        helpText="Self-occupied property — cap ₹2,00,000. Old regime only."
        {...register('home_loan_interest', { valueAsNumber: true })}
      />

      <CurrencyInput
        label="Savings Interest 80TTA / 80TTB"
        error={errors.savings_interest_80tta?.message}
        helpText="Under 60: up to ₹10,000 (80TTA). 60+: up to ₹50,000 (80TTB). Old regime only."
        {...register('savings_interest_80tta', { valueAsNumber: true })}
      />
    </div>
  )
}
