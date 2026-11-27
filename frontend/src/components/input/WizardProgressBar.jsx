import { Check } from 'lucide-react'

const STEP_LABELS = ['Income', 'Deductions', 'Housing', 'Other', 'Review']

/**
 * Props:
 *   currentStep (number, 0-indexed)
 *   totalSteps (number)
 */
export default function WizardProgressBar({ currentStep, totalSteps = 5 }) {
  const labels = STEP_LABELS.slice(0, totalSteps)

  return (
    <nav aria-label="Form progress" className="mb-8">
      <p className="mb-3 text-sm font-medium text-muted sm:hidden">
        Step {currentStep + 1} of {totalSteps}
        <span className="text-ink"> · {labels[currentStep]}</span>
      </p>
      <ol className="flex items-start">
        {labels.map((label, i) => {
          const isDone = i < currentStep
          const isCurrent = i === currentStep

          return (
            <li
              key={i}
              aria-current={isCurrent ? 'step' : undefined}
              className="flex flex-1 flex-col items-center"
            >
              <div className="flex w-full items-center">
                <div
                  className={[
                    'h-0.5 flex-1 rounded-full transition-colors',
                    i === 0 ? 'invisible' : i <= currentStep ? 'bg-brand-600' : 'bg-line',
                  ].join(' ')}
                />
                <div
                  className={[
                    'flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors',
                    isDone
                      ? 'bg-brand-600 text-white'
                      : isCurrent
                        ? 'bg-brand-600 text-white ring-4 ring-brand-100'
                        : 'border border-line bg-white text-subtle',
                  ].join(' ')}
                >
                  {isDone ? <Check className="h-4 w-4" aria-hidden="true" /> : i + 1}
                </div>
                <div
                  className={[
                    'h-0.5 flex-1 rounded-full transition-colors',
                    i === totalSteps - 1 ? 'invisible' : i < currentStep ? 'bg-brand-600' : 'bg-line',
                  ].join(' ')}
                />
              </div>
              <span
                className={[
                  'mt-2 hidden text-xs font-medium sm:block',
                  isCurrent ? 'text-ink' : isDone ? 'text-brand-700' : 'text-subtle',
                ].join(' ')}
              >
                {label}
              </span>
              <span className="sr-only sm:hidden">{label}</span>
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
