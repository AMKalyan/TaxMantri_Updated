import { useState } from 'react'
import { ChevronDown, Loader2 } from 'lucide-react'
import { getITR1Mapping } from '../../api/endpoints.js'
import { Card, formatINR } from '../ui'

/**
 * Lazy-fetch collapsible ITR-1 field mapping table.
 *
 * Props:
 *   profileId (string)
 */
export default function ITR1Table({ profileId }) {
  const [expanded, setExpanded] = useState(false)
  const [loading, setLoading] = useState(false)
  const [mapping, setMapping] = useState(null)
  const [error, setError] = useState(null)

  const handleToggle = async () => {
    if (!expanded && !mapping && !loading) {
      // First open — fetch data
      setLoading(true)
      setError(null)
      try {
        const data = await getITR1Mapping(profileId)
        setMapping(data)
      } catch {
        setError('Could not load ITR-1 mapping.')
      } finally {
        setLoading(false)
      }
    }
    setExpanded((prev) => !prev)
  }

  const oldEntries = mapping?.filter((e) => e.regime === 'old') ?? []
  const newEntries = mapping?.filter((e) => e.regime === 'new') ?? []
  const commonEntries = mapping?.filter((e) => !e.regime || e.regime === 'both') ?? []

  return (
    <Card className="overflow-hidden">
      {/* Toggle header */}
      <button
        type="button"
        onClick={handleToggle}
        aria-expanded={expanded}
        className="flex min-h-[44px] w-full items-center justify-between gap-3 px-5 py-4 text-left transition-colors hover:bg-surface"
      >
        <div>
          <h3 className="font-semibold text-ink">ITR-1 Sahaj Field Mapping</h3>
          <p className="mt-0.5 text-sm text-muted">See how your numbers map to ITR-1 form fields</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {loading && <Loader2 className="h-4 w-4 animate-spin text-brand-700" />}
          <ChevronDown
            className={['h-5 w-5 text-subtle transition-transform', expanded ? 'rotate-180' : ''].join(' ')}
          />
        </div>
      </button>

      {/* Content */}
      {expanded && (
        <div className="border-t border-line p-4 sm:p-5">
          {error ? (
            <p className="py-4 text-center text-sm text-red-700">{error}</p>
          ) : loading ? (
            <div className="flex items-center justify-center gap-2 py-8 text-muted">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span className="text-sm">Loading field mapping…</span>
            </div>
          ) : mapping ? (
            <div className="space-y-6">
              {[
                { label: 'Common Fields (Both Regimes)', entries: commonEntries },
                { label: 'Old Regime Fields', entries: oldEntries },
                { label: 'New Regime Fields', entries: newEntries },
              ].map(({ label, entries }) => {
                if (entries.length === 0) return null
                return (
                  <div key={label}>
                    <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-subtle">{label}</h4>
                    {/* Scrolls sideways on narrow screens */}
                    <div className="overflow-x-auto rounded-xl border border-line">
                      <table className="w-full min-w-[520px] text-sm">
                        <thead>
                          <tr className="border-b border-line bg-surface">
                            <th className="sticky top-0 bg-surface px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted">ITR-1 Field</th>
                            <th className="sticky top-0 bg-surface px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted">Schedule</th>
                            <th className="sticky top-0 bg-surface px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {entries.map((entry, i) => (
                            <tr key={i} className="odd:bg-surface">
                              <td className="px-4 py-2.5 text-ink">{entry.itr1_field}</td>
                              <td className="px-4 py-2.5 text-xs text-muted">{entry.schedule}</td>
                              <td className="tabular whitespace-nowrap px-4 py-2.5 text-right font-semibold text-ink">
                                {formatINR(entry.value)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    {entries.some((e) => e.note) && (
                      <div className="mt-2 space-y-1">
                        {entries.filter((e) => e.note).map((e, i) => (
                          <p key={i} className="text-xs italic text-subtle">
                            * {e.itr1_field}: {e.note}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : null}
        </div>
      )}
    </Card>
  )
}
