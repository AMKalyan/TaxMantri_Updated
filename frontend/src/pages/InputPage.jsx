import { Link } from 'react-router-dom'
import SampleProfileButton from '../components/common/SampleProfileButton.jsx'
import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { ShieldCheck } from 'lucide-react'
import InputTabs from '../components/input/InputTabs.jsx'
import LoadingOverlay from '../components/common/LoadingOverlay.jsx'
import { Card, Eyebrow } from '../components/ui'

/**
 * The state bridge between InputTabs and ResultsPage.
 *
 * Flow:
 *   1. Child tab calls onCalculationComplete(profileId, taxResult)
 *   2. InputPage stores {profileId, taxResult} in pendingNavigation
 *   3. Shows LoadingOverlay
 *   4. LoadingOverlay.onComplete fires → navigate to /results/:id
 *      passing taxResult as router state (no refetch needed)
 */
export default function InputPage() {
  const navigate = useNavigate()
  const [isCalculating, setIsCalculating] = useState(false)
  const [pendingNavigation, setPendingNavigation] = useState(null)

  const handleCalculationComplete = useCallback((profileId, taxResult) => {
    setPendingNavigation({ profileId, taxResult })
    setIsCalculating(true)
  }, [])

  const handleOverlayComplete = useCallback(() => {
    if (pendingNavigation) {
      navigate(`/results/${pendingNavigation.profileId}`, {
        state: { taxResult: pendingNavigation.taxResult },
      })
    }
  }, [navigate, pendingNavigation])

  return (
    <div className="relative min-h-screen bg-white font-sans text-ink">
      <LoadingOverlay visible={isCalculating} onComplete={handleOverlayComplete} />

      <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-10 sm:px-6 sm:pt-14">
        <div className="mb-8 text-center">
          <Eyebrow>FY 2025-26 · AY 2026-27</Eyebrow>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
            Enter your tax details
          </h1>
          <p className="mx-auto mt-3 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
            Upload Form 16 for automatic extraction, or enter details manually.
          </p>
          <div className="mt-5 flex justify-center">
            <SampleProfileButton label="Just exploring? Try a sample profile" />
          </div>
        </div>

        <Card className="p-4 sm:p-6 md:p-8">
          <InputTabs
            onCalculationComplete={handleCalculationComplete}
            onCalculating={setIsCalculating}
          />
        </Card>

        <p className="mt-6 flex items-start justify-center gap-2 text-center text-sm text-muted">
          <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-brand-600" aria-hidden="true" />
          <span>
            No account needed. Your figures are deleted automatically after 24 hours —{' '}
            <Link to="/privacy" className="font-medium text-ink underline underline-offset-2 hover:text-brand-700">
              privacy details
            </Link>.
          </span>
        </p>
      </main>
    </div>
  )
}
