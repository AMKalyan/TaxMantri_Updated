import { ArrowRight, Calculator, FileText, MessageSquareText, ShieldCheck, Trash2, UserX } from 'lucide-react'
import SampleProfileButton from '../components/common/SampleProfileButton.jsx'
import { Badge, Button, Card, Eyebrow, Section, formatINR } from '../components/ui'

// Engine output for SAMPLE_PROFILE (components/common/SampleProfileButton.jsx):
// ₹15.6L salary, metro rent, full 80C/80D/NPS. Kept in sync by the golden tests.
const PREVIEW = { old: 139650, new: 106860, salary: 1560000 }

const FEATURES = [
  {
    icon: FileText,
    title: 'Reads your Form 16',
    body: 'Upload the PDF or a photo. Salary, exemptions and deductions are filled in for you to review and edit.',
  },
  {
    icon: Calculator,
    title: 'Exact Old vs New comparison',
    body: 'A rule-based engine applies the FY 2025-26 slabs, 87A rebate, HRA and every deduction — no guesswork.',
  },
  {
    icon: MessageSquareText,
    title: 'Ask "what if…?"',
    body: 'The assistant answers tax questions with section references and re-runs your numbers for scenarios like more NPS.',
  },
]

const STEPS = [
  { n: '1', title: 'Add your details', body: 'Upload Form 16 or fill a five-step form. About two minutes.' },
  { n: '2', title: 'See both regimes', body: 'Tax under each regime, side by side, with the cheaper one highlighted.' },
  { n: '3', title: 'Act on it', body: 'Unused deductions, ITR-1 field mapping and a PDF summary to file with.' },
]

const TRUST = [
  { icon: ShieldCheck, text: 'Numbers come from a tested tax engine, not an AI guess' },
  { icon: Trash2, text: 'Your figures are deleted automatically after 24 hours' },
  { icon: UserX, text: 'No account, no PAN, no name stored' },
]

function PreviewCard() {
  const saving = PREVIEW.old - PREVIEW.new
  return (
    <Card className="w-full max-w-md p-5 shadow-lift sm:p-6">
      <div className="flex items-center justify-between">
        <p className="text-sm font-medium text-muted">Sample · {formatINR(PREVIEW.salary)} salary</p>
        <Badge tone="neutral">AY 2026-27</Badge>
      </div>
      <div className="mt-5 grid grid-cols-2 gap-3">
        <div className="rounded-xl border border-line p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-subtle">Old regime</p>
          <p className="tabular mt-1 text-xl font-bold text-ink sm:text-2xl">{formatINR(PREVIEW.old)}</p>
        </div>
        <div className="rounded-xl border-2 border-brand-600 bg-brand-50 p-4">
          <p className="text-xs font-medium uppercase tracking-wide text-brand-700">New regime</p>
          <p className="tabular mt-1 text-xl font-bold text-ink sm:text-2xl">{formatINR(PREVIEW.new)}</p>
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between rounded-xl bg-ink px-4 py-3 text-white">
        <span className="text-sm">New regime saves</span>
        <span className="tabular text-lg font-bold">{formatINR(saving)}</span>
      </div>
    </Card>
  )
}

export default function HeroPage() {
  return (
    <div className="flex min-h-screen flex-col bg-white">

      <main className="flex-1">
        {/* Hero */}
        <div className="border-b border-line bg-gradient-to-b from-brand-50/60 to-white">
          <Section className="grid items-center gap-12 py-14 sm:py-20 lg:grid-cols-[1.1fr_1fr]">
            <div>
              <Badge tone="brand">Updated for FY 2025-26 · AY 2026-27</Badge>
              <h1 className="mt-5 text-4xl font-extrabold leading-[1.1] tracking-tight text-ink sm:text-5xl">
                Old or New regime?<br />Know your exact tax in two minutes.
              </h1>
              <p className="mt-5 max-w-xl text-lg leading-relaxed text-muted">
                TaxMantri reads your Form 16, calculates your tax under both regimes, and shows the deductions
                you're missing — free, for salaried ITR-1 filers.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Button to="/input" size="lg">
                  Calculate my tax <ArrowRight className="h-4 w-4" />
                </Button>
                <SampleProfileButton label="See a sample result" />
              </div>
            </div>
            <div className="flex justify-center lg:justify-end">
              <PreviewCard />
            </div>
          </Section>
        </div>

        {/* Features */}
        <Section className="py-16 sm:py-20">
          <Eyebrow>What it does</Eyebrow>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-ink">Everything you need before filing ITR-1</h2>
          <div className="mt-10 grid gap-5 md:grid-cols-3">
            {FEATURES.map(({ icon: Icon, title, body }) => (
              <Card key={title} className="p-6">
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                  <Icon className="h-5 w-5" />
                </span>
                <h3 className="mt-4 text-lg font-semibold text-ink">{title}</h3>
                <p className="mt-2 leading-relaxed text-muted">{body}</p>
              </Card>
            ))}
          </div>
        </Section>

        {/* How it works */}
        <div className="border-y border-line bg-surface">
          <Section className="py-16 sm:py-20">
            <Eyebrow>How it works</Eyebrow>
            <h2 className="mt-2 text-3xl font-bold tracking-tight text-ink">Three steps</h2>
            <ol className="mt-10 grid gap-8 md:grid-cols-3">
              {STEPS.map((s) => (
                <li key={s.n} className="flex gap-4">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-ink text-sm font-bold text-white">{s.n}</span>
                  <div>
                    <h3 className="font-semibold text-ink">{s.title}</h3>
                    <p className="mt-1 leading-relaxed text-muted">{s.body}</p>
                  </div>
                </li>
              ))}
            </ol>
            <Button to="/how-it-works" variant="secondary" className="mt-10">
              Read the details <ArrowRight className="h-4 w-4" />
            </Button>
          </Section>
        </div>

        {/* Trust + CTA */}
        <Section className="py-16 sm:py-20">
          <div className="grid gap-4 sm:grid-cols-3">
            {TRUST.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-start gap-3">
                <Icon className="mt-0.5 h-5 w-5 shrink-0 text-brand-700" />
                <p className="text-sm leading-relaxed text-muted">{text}</p>
              </div>
            ))}
          </div>
          <div className="mt-12 flex flex-col items-start gap-5 rounded-2xl bg-ink p-8 text-white shadow-lift sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-2xl font-bold">Ready to compare?</h2>
              <p className="mt-1 text-slate-300">No sign-up. Your numbers in about two minutes.</p>
            </div>
            <Button to="/input" size="lg" className="w-full sm:w-auto">
              Calculate my tax <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </Section>
      </main>

    </div>
  )
}
