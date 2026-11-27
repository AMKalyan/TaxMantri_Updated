import { forwardRef, useId } from 'react'

/**
 * ₹-prefixed currency number input.
 *
 * Props (in addition to standard HTML input props):
 *   label     (string)  — field label above
 *   error     (string)  — validation error message below
 *   helpText  (string)  — subtle helper below field
 *   required  (bool)    — shows asterisk on label
 */
const CurrencyInput = forwardRef(function CurrencyInput(
  { label, error, helpText, required, className = '', onFocus, onChange, ...props },
  ref,
) {
  const autoId = useId()
  const inputId = props.id ?? autoId
  const noteId = `${inputId}-note`

  // When the field is focused and currently shows 0, clear it so the user can
  // type without "0" being prepended to their input.
  const handleFocus = (e) => {
    if (e.target.value === '0' || e.target.value === '') {
      e.target.value = ''
    }
    onFocus?.(e)
  }

  // When the field is cleared (user deleted everything), set it to '' so
  // react-hook-form receives an empty string → NaN → gets coerced to 0 by
  // the NaN-cleanup in ManualWizard before submission.
  const handleChange = (e) => {
    onChange?.(e)
  }

  const note = error || helpText

  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-ink">
          {label}
          {required && <span className="ml-1 text-red-600">*</span>}
        </label>
      )}
      <div className="relative">
        <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 select-none text-sm font-medium text-subtle">
          ₹
        </span>
        <input
          ref={ref}
          id={inputId}
          type="number"
          inputMode="numeric"
          min={0}
          step={1}
          placeholder="0"
          aria-invalid={error ? true : undefined}
          aria-describedby={note ? noteId : undefined}
          onFocus={handleFocus}
          onChange={handleChange}
          className={[
            'tabular w-full min-h-[44px] rounded-xl border bg-white pl-8 pr-3.5 py-2.5 text-base text-ink transition-colors sm:text-sm',
            'placeholder:text-subtle/70 focus:outline-none focus:ring-2',
            error
              ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
              : 'border-line hover:border-slate-300 focus:border-brand-600 focus:ring-brand-500/30',
            className,
          ].join(' ')}
          {...props}
        />
      </div>
      {error && (
        <p id={noteId} className="text-xs font-medium text-red-600">{error}</p>
      )}
      {helpText && !error && (
        <p id={noteId} className="text-xs text-subtle">{helpText}</p>
      )}
    </div>
  )
})

export default CurrencyInput
