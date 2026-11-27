import { Link } from 'react-router-dom'

const cx = (...c) => c.filter(Boolean).join(' ')

const BUTTON_VARIANTS = {
  primary: 'bg-brand-600 text-white hover:bg-brand-700 shadow-card',
  secondary: 'bg-white text-ink border border-line hover:bg-surface hover:border-slate-300',
  ghost: 'text-muted hover:text-ink hover:bg-surface',
  danger: 'bg-white text-red-700 border border-red-200 hover:bg-red-50',
}
const BUTTON_SIZES = {
  sm: 'min-h-[36px] px-3.5 text-sm',
  md: 'min-h-[44px] px-5 text-sm',
  lg: 'min-h-[52px] px-6 text-base',
}

/** Button that renders as <Link> when `to` is given, <a> for `href`, else <button>. */
export function Button({ variant = 'primary', size = 'md', className, to, href, children, ...props }) {
  const classes = cx(
    'inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-colors',
    'disabled:cursor-not-allowed disabled:opacity-60',
    BUTTON_VARIANTS[variant],
    BUTTON_SIZES[size],
    className,
  )
  if (to) return <Link to={to} className={classes} {...props}>{children}</Link>
  if (href) return <a href={href} className={classes} {...props}>{children}</a>
  return <button type="button" className={classes} {...props}>{children}</button>
}

export function Card({ className, children, as: Tag = 'div', ...props }) {
  return (
    <Tag className={cx('rounded-2xl border border-line bg-white shadow-card', className)} {...props}>
      {children}
    </Tag>
  )
}

const BADGE_TONES = {
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
  neutral: 'bg-surface text-muted ring-line',
  warning: 'bg-amber-50 text-amber-800 ring-amber-200',
}

export function Badge({ tone = 'neutral', className, children }) {
  return (
    <span className={cx('inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset', BADGE_TONES[tone], className)}>
      {children}
    </span>
  )
}

/** Page-width section with consistent gutters. */
export function Section({ className, children, ...props }) {
  return (
    <section className={cx('mx-auto w-full max-w-page px-4 sm:px-6', className)} {...props}>
      {children}
    </section>
  )
}

export function Eyebrow({ children }) {
  return <p className="text-sm font-semibold uppercase tracking-wide text-brand-700">{children}</p>
}

/** ₹ amount with Indian digit grouping and no decimals. */
export function formatINR(value) {
  const n = Math.round(Number(value) || 0)
  return `₹${n.toLocaleString('en-IN')}`
}

export function Footer() {
  return (
    <footer className="border-t border-line bg-surface">
      <Section className="flex flex-col gap-4 py-8 text-sm text-subtle sm:flex-row sm:items-center sm:justify-between">
        <p>
          <span className="font-semibold text-ink">TaxMantri</span> · AY 2026-27 · For education only — consult a CA before filing.
        </p>
        <nav className="flex flex-wrap gap-x-5 gap-y-2">
          <Link to="/how-it-works" className="hover:text-ink">How it works</Link>
          <Link to="/about" className="hover:text-ink">About</Link>
          <Link to="/privacy" className="hover:text-ink">Privacy</Link>
        </nav>
      </Section>
    </footer>
  )
}
