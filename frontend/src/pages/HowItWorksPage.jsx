import { ArrowRight, BarChart, BookOpen, CheckCircle2, FileText, Settings, ShieldCheck, Zap } from 'lucide-react'
import { Badge, Button, Card, Eyebrow, Section } from '../components/ui'

const steps = [
  {
    icon: Settings,
    title: 'Choose how you want to start',
    description: 'TaxMantri supports two paths, so it works whether or not you have your Form 16 handy.',
    options: [
      { title: 'Upload Form 16', desc: 'OCR extracts your salary details automatically. Low-confidence fields are highlighted for review.' },
      { title: 'Enter details manually', desc: 'A guided 5-step form covers personal details, salary, HRA, investments and more.' },
    ],
  },
  {
    icon: FileText,
    title: 'Data extraction and review',
    description:
      'If you upload Form 16, OCR reads key fields like salary, HRA and TDS. Confidence scores flag uncertain values, and you can edit any field before continuing — so you stay in control of every number.',
  },
  {
    icon: BarChart,
    title: 'Your financial profile is built',
    description:
      'Once confirmed, your data becomes a structured profile: salary components, HRA, investments, health insurance and loan interest. This profile powers every calculation.',
  },
  {
    icon: Zap,
    title: 'Deterministic tax engine',
    description:
      'A pure rule-based engine (not AI) calculates your tax, so the numbers are exact and repeatable. It computes the Old Regime (HRA, standard deduction, 80C/80D, 87A) and the New Regime, then recommends the one with lower tax.',
  },
  {
    icon: CheckCircle2,
    title: 'Regime comparison and optimizer',
    description:
      "Side-by-side cards show total tax payable, your savings and the deduction breakdown. The optimizer points out unused deductions — for example, 'Invest ₹38,000 more under 80C to save ₹11,400'.",
  },
  {
    icon: BookOpen,
    title: 'An assistant grounded in the law',
    description:
      "Gemini explains results and answers your questions. Its answers are grounded in Income Tax Act passages found by hybrid retrieval — semantic and keyword search combined — and for any figure it calls the same tax engine instead of guessing.",
  },
  {
    icon: ShieldCheck,
    title: 'Privacy by default',
    description:
      "Uploaded Form 16 files are deleted as soon as the numbers are read, and your name and PAN are never stored. Your figures are deleted automatically after 24 hours, or instantly with 'Delete my data'. The assistant only receives a numeric summary of your profile, and all traffic uses HTTPS.",
  },
]

export default function HowItWorksPage() {
  return (
    <div className="bg-white">
      <div className="border-b border-line bg-gradient-to-b from-brand-50/60 to-white">
        <Section className="py-12 sm:py-16">
          <Badge tone="brand">Your tax co-pilot</Badge>
          <h1 className="mt-4 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
            From Form 16 to filing, in minutes
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">
            TaxMantri turns complex tax rules into clear, actionable guidance for salaried individuals.
          </p>
        </Section>
      </div>

      <Section className="py-12 sm:py-16">
        <Eyebrow>How it works</Eyebrow>
        <h2 className="mt-2 text-2xl font-bold tracking-tight text-ink sm:text-3xl">Step by step</h2>
        <ol className="mt-8 space-y-4">
          {steps.map(({ icon: Icon, title, description, options }, idx) => (
            <Card as="li" key={title} className="flex flex-col gap-4 p-5 sm:flex-row sm:gap-5 sm:p-6">
              <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
                <Icon className="h-5 w-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-subtle">Step {idx + 1}</p>
                <h3 className="mt-1 text-lg font-semibold text-ink">{title}</h3>
                <p className="mt-2 leading-relaxed text-muted">{description}</p>
                {options && (
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    {options.map((opt) => (
                      <div key={opt.title} className="rounded-xl border border-line bg-surface p-4">
                        <h4 className="font-semibold text-ink">{opt.title}</h4>
                        <p className="mt-1 text-sm leading-relaxed text-muted">{opt.desc}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </ol>

        <div className="mt-12 flex flex-col items-start gap-5 rounded-2xl bg-ink p-6 text-white shadow-lift sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <div>
            <h2 className="text-2xl font-bold">Tax smarter, save better.</h2>
            <p className="mt-1 text-slate-300">Turn tax filing from guesswork into guided, accurate decisions.</p>
          </div>
          <Button to="/input" size="lg" className="w-full sm:w-auto">
            Calculate my tax <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </Section>
    </div>
  )
}
