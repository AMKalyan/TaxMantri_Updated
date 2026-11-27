import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { useEffect } from 'react'
import { RotateCcw, Pencil, ShieldCheck } from 'lucide-react'
import SavingsBanner from '../components/results/SavingsBanner.jsx'
import AIInsightsCard from '../components/results/AIInsightsCard.jsx'
import RegimeCardPair from '../components/results/RegimeCardPair.jsx'
import ITR1Table from '../components/results/ITR1Table.jsx'
import DeleteDataButton from '../components/results/DeleteDataButton.jsx'
import PDFDownloadButton from '../components/results/PDFDownloadButton.jsx'
import { Button, Card, Eyebrow } from '../components/ui'

/**
 * Results page — renders immediately from router state (no API refetch).
 * Profile ID from URL params is used for lazy PDF + ITR-1 mapping requests.
 *
 * Fallback: if user refreshes (router state lost), shows "Start Over" prompt.
 */
export default function ResultsPage() {
  const { profileId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const taxResult = state?.taxResult ?? null

  // Persist profileId so ChatWidget can personalise answers with the current session
  useEffect(() => {
    if (profileId) localStorage.setItem('taxmantri_profile_id', profileId)
  }, [profileId])

  // Fallback: page refresh lost router state
  if (!taxResult) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center bg-white px-4 py-16">
        <Card className="w-full max-w-sm p-8 text-center">
          <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-xl bg-surface text-subtle">
            <RotateCcw className="h-6 w-6" />
          </span>
          <h2 className="mt-5 text-2xl font-bold text-ink">Session expired</h2>
          <p className="mt-2 text-muted">
            Your results aren't available after a page refresh. Please start over.
          </p>
          <Button size="lg" className="mt-6 w-full" onClick={() => navigate('/input')}>
            Start Over
          </Button>
        </Card>
      </div>
    )
  }

  return (
    <div className="overflow-x-hidden bg-white">
      <main className="mx-auto max-w-4xl space-y-6 px-4 pb-16 pt-8 sm:px-6 sm:pt-10">
        {/* Title */}
        <div>
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Eyebrow>AY 2026-27</Eyebrow>
              <h1 className="mt-1 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">Your Tax Analysis</h1>
            </div>
            <div className="flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => navigate('/input')}>
                <Pencil className="h-4 w-4" />
                Edit details
              </Button>
              {/* The navbar shows this on desktop; phones get it here. */}
              <div className="md:hidden">
                <PDFDownloadButton profileId={profileId} />
              </div>
            </div>
          </div>
          <p className="mt-2 text-muted">
            Old vs New Regime comparison for AY 2026-27. Tap a card to see the full breakdown.
          </p>
          {state?.isSample && (
            <p className="mt-4 rounded-xl bg-amber-50 px-3.5 py-2.5 text-sm font-medium text-amber-800 ring-1 ring-inset ring-amber-200">
              Sample profile — ₹15.6L salary, metro rent, full 80C/80D/NPS. Enter your own details for real numbers.
            </p>
          )}
        </div>

        <SavingsBanner taxResult={taxResult} />

        {/* Rationale, IT Act citations, law context */}
        <AIInsightsCard taxResult={taxResult} />

        <RegimeCardPair taxResult={taxResult} />

        {/* ITR-1 mapping (lazy) */}
        <ITR1Table profileId={profileId} />

        {/* Privacy */}
        <Card className="flex flex-col items-start gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" />
            <p className="text-sm text-muted">
              Your figures are deleted automatically after 24 hours. Want them gone now?
            </p>
          </div>
          <DeleteDataButton profileId={profileId} />
        </Card>

        <p className="pb-4 text-center text-xs text-subtle">
          For educational purposes only. Consult a CA before filing ITR-1.
          Tax calculated on AY 2026-27 (FY 2025-26) rules.
        </p>
      </main>
    </div>
  )
}
