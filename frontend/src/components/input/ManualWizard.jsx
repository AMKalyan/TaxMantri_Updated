import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import toast from 'react-hot-toast'
import WizardProgressBar from './WizardProgressBar.jsx'
import Step1Income from './steps/Step1Income.jsx'
import Step2Deductions from './steps/Step2Deductions.jsx'
import Step3Housing from './steps/Step3Housing.jsx'
import Step4Other from './steps/Step4Other.jsx'
import Step5Review from './steps/Step5Review.jsx'
import ErrorBanner from '../common/ErrorBanner.jsx'
import { Button } from '../ui'
import { createProfile, calculateTax } from '../../api/endpoints.js'

// ---- Zod schema ----
// Optional ₹ fields: an emptied input gives NaN from valueAsNumber; treat it as 0.
const optionalAmount = (num) =>
  z.preprocess((v) => (v === '' || v == null || Number.isNaN(v) ? 0 : v), num)

const schema = z.object({
  // Step 1 — Income
  basic_salary: z.number({ invalid_type_error: 'Required' }).min(0, 'Must be ≥ 0').max(5000000, 'ITR-1 limit: Basic salary cannot exceed ₹50,00,000'),
  hra_received: optionalAmount(z.number().min(0)),
  lta: optionalAmount(z.number().min(0)),
  special_allowance: optionalAmount(z.number().min(0)),
  other_allowances: optionalAmount(z.number().min(0)),
  professional_tax: optionalAmount(z.number().min(0).max(2500, 'Max ₹2,500')),

  // Step 2 — Deductions
  investments_80c: optionalAmount(z.number().min(0).max(150000, 'Max ₹1,50,000')),
  health_insurance_self: optionalAmount(z.number().min(0)),
  health_insurance_parents: optionalAmount(z.number().min(0)),
  parent_senior_citizen: z.boolean().default(false).optional(),
  employee_nps_80ccd1b: optionalAmount(z.number().min(0).max(50000, 'Max ₹50,000')),
  employer_nps_80ccd2: optionalAmount(z.number().min(0)),
  home_loan_interest: optionalAmount(z.number().min(0).max(200000, 'Max ₹2,00,000')),
  savings_interest_80tta: optionalAmount(z.number().min(0)),

  // Step 3 — Housing
  monthly_rent_paid: optionalAmount(z.number().min(0)),
  city_type: z.enum(['metro', 'non_metro'], { required_error: 'Select city type' }),

  // Step 4 — Other
  age_bracket: z.enum(['under60', '60_79', '80plus'], { required_error: 'Select age bracket' }),
  other_income: optionalAmount(z.number().min(0)),
})

// Which fields belong to each step (for per-step validation trigger)
const STEP_FIELDS = [
  ['basic_salary', 'hra_received', 'lta', 'special_allowance', 'other_allowances', 'professional_tax'],
  ['investments_80c', 'health_insurance_self', 'health_insurance_parents', 'parent_senior_citizen', 'employee_nps_80ccd1b', 'employer_nps_80ccd2', 'home_loan_interest', 'savings_interest_80tta'],
  ['monthly_rent_paid', 'city_type'],
  ['age_bracket', 'other_income'],
  [], // review — no new fields
]

const TOTAL_STEPS = 5

/**
 * Props:
 *   onCalculationComplete (fn) — called with (profileId, taxResult)
 *   onCalculating (fn)         — called with bool
 */
const FORM_STORAGE_KEY = 'taxmantri_last_form'

/** Reads saved form values from localStorage (returns {} if none saved yet) */
function getSavedFormValues() {
  try {
    const raw = localStorage.getItem(FORM_STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch {
    return {}
  }
}

export default function ManualWizard({ onCalculationComplete, onCalculating }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [apiError, setApiError] = useState(null)

  const saved = getSavedFormValues()

  const {
    register,
    handleSubmit,
    trigger,
    getValues,
    control,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      basic_salary: saved.basic_salary ?? undefined,
      hra_received: saved.hra_received ?? 0,
      lta: saved.lta ?? 0,
      special_allowance: saved.special_allowance ?? 0,
      other_allowances: saved.other_allowances ?? 0,
      professional_tax: saved.professional_tax ?? 0,
      investments_80c: saved.investments_80c ?? 0,
      health_insurance_self: saved.health_insurance_self ?? 0,
      health_insurance_parents: saved.health_insurance_parents ?? 0,
      parent_senior_citizen: saved.parent_senior_citizen ?? false,
      employee_nps_80ccd1b: saved.employee_nps_80ccd1b ?? 0,
      employer_nps_80ccd2: saved.employer_nps_80ccd2 ?? 0,
      home_loan_interest: saved.home_loan_interest ?? 0,
      savings_interest_80tta: saved.savings_interest_80tta ?? 0,
      monthly_rent_paid: saved.monthly_rent_paid ?? 0,
      city_type: saved.city_type ?? 'metro',
      age_bracket: saved.age_bracket ?? 'under60',
      other_income: saved.other_income ?? 0,
    },
    mode: 'onTouched',
  })

  const goNext = async () => {
    const fields = STEP_FIELDS[step]
    if (fields.length > 0) {
      const valid = await trigger(fields)
      if (!valid) return
    }
    if (step < TOTAL_STEPS - 1) setStep((s) => s + 1)
  }

  const goBack = () => {
    if (step > 0) setStep((s) => s - 1)
  }

  const onSubmit = async (data) => {
    setApiError(null)
    onCalculating?.(true)

    try {
      const payload = {
        ...data,
        input_method: 'manual',
        // Ensure NaN values (empty number inputs) become 0
        ...Object.fromEntries(
          Object.entries(data).map(([k, v]) => [k, typeof v === 'number' && isNaN(v) ? 0 : v]),
        ),
      }

      // Persist form values so the user can go back and edit without re-typing
      localStorage.setItem(FORM_STORAGE_KEY, JSON.stringify(payload))

      const profileResult = await createProfile(payload)
      const profileId = profileResult.profile_id

      const taxResult = await calculateTax(profileId)
      onCalculationComplete?.(profileId, taxResult)
    } catch (err) {
      onCalculating?.(false)
      const errData = err?.response?.data
      setApiError(errData ?? 'Calculation failed. Please try again.')
      toast.error('Something went wrong. Check your inputs.')
    }
  }

  const renderStep = () => {
    switch (step) {
      case 0: return <Step1Income register={register} errors={errors} />
      case 1: return <Step2Deductions register={register} errors={errors} control={control} />
      case 2: return <Step3Housing register={register} errors={errors} />
      case 3: return <Step4Other register={register} errors={errors} />
      case 4: return <Step5Review values={getValues()} />
      default: return null
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <WizardProgressBar currentStep={step} totalSteps={TOTAL_STEPS} />

      <ErrorBanner error={apiError} onDismiss={() => setApiError(null)} />

      <div className="min-h-[360px]">
        {renderStep()}
      </div>

      {/* Navigation */}
      <div className="mt-8 flex flex-col-reverse gap-3 border-t border-line pt-6 sm:flex-row sm:items-center">
        {step > 0 && (
          <Button
            key="back"
            variant="secondary"
            onClick={goBack}
            className="w-full sm:w-auto"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
            Back
          </Button>
        )}

        {step < TOTAL_STEPS - 1 ? (
          <Button
            key="next"
            onClick={goNext}
            className="w-full sm:ml-auto sm:w-auto"
          >
            Next
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        ) : (
          <Button
            key="submit"
            type="submit"
            className="w-full sm:ml-auto sm:w-auto sm:px-8"
          >
            Calculate my tax
          </Button>
        )}
      </div>
    </form>
  )
}
