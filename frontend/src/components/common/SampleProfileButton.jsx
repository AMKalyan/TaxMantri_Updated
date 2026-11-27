import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Sparkles } from 'lucide-react'
import { createProfile, calculateTax } from '../../api/endpoints.js'
import { Button } from '../ui/index.jsx'

/** A typical metro salaried profile used for the "try it without your data" demo. */
export const SAMPLE_PROFILE = {
  input_method: 'manual',
  basic_salary: 900000,
  hra_received: 360000,
  special_allowance: 300000,
  monthly_rent_paid: 25000,
  city_type: 'metro',
  age_bracket: 'under60',
  professional_tax: 2400,
  investments_80c: 150000,
  health_insurance_self: 25000,
  employee_nps_80ccd1b: 50000,
  parent_senior_citizen: false,
}

/**
 * Runs the full calculation on a made-up profile so visitors can explore the
 * results page without entering anything personal.
 */
export default function SampleProfileButton({ className = '', label = 'Try with a sample profile' }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  const run = async () => {
    setBusy(true)
    try {
      const { profile_id } = await createProfile(SAMPLE_PROFILE)
      const taxResult = await calculateTax(profile_id)
      navigate(`/results/${profile_id}`, { state: { taxResult, isSample: true } })
    } catch {
      setBusy(false) // the API client already shows a toast
    }
  }

  return (
    <Button variant="secondary" size="lg" onClick={run} disabled={busy} className={className}>
      <Sparkles className="h-4 w-4 text-brand-600" />
      {busy ? 'Calculating sample…' : label}
    </Button>
  )
}
