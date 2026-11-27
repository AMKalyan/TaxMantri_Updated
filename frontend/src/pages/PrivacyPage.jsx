import { ArrowLeft } from 'lucide-react'
import { Button, Card, Eyebrow, Section } from '../components/ui'

const RETENTION_HOURS = 24

function Block({ title, children }) {
  return (
    <Card className="p-5 sm:p-6">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <div className="mt-3 space-y-2 leading-relaxed text-muted">{children}</div>
    </Card>
  )
}

export default function PrivacyPage() {
  return (
    <div className="bg-white">
      <Section className="py-12 sm:py-16">
        <div className="max-w-3xl">
        <Eyebrow>Privacy</Eyebrow>
        <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">How we handle your data</h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">
          TaxMantri is a free educational tool. It is not a tax filing service and does not replace advice from a
          chartered accountant.
        </p>

        <div className="mt-8 space-y-4">
          <Block title="What we store">
            <ul className="list-disc space-y-2 pl-5">
              <li>The salary and deduction figures you enter or that are read from your Form 16.</li>
              <li>Your tax results, and the questions you ask the assistant with its answers.</li>
              <li>
                We do <strong className="text-ink">not</strong> store your name, PAN, address or the Form 16 file itself.
                Uploaded files are deleted immediately after the numbers are read.
              </li>
            </ul>
          </Block>

          <Block title="How long">
            <p>
              Everything is deleted automatically after {RETENTION_HOURS} hours. You can delete it sooner with the
              <strong className="text-ink"> Delete my data</strong> button on the results page.
            </p>
          </Block>

          <Block title="Who processes it">
            <ul className="list-disc space-y-2 pl-5">
              <li>
                Questions to the assistant and a numeric summary of your profile (no name or PAN) are sent to Google's
                Gemini API to generate answers. TaxMantri uses Gemini's free tier, under which Google may use prompts to
                improve its products — so please don't type personal identifiers (name, PAN, account numbers) into the chat.
              </li>
              <li>The app runs on Render (backend), Vercel (website), Neon (database) and Upstash (cache).</li>
            </ul>
          </Block>

          <Block title="No accounts, no tracking">
            <p>There are no logins, no advertising and no third-party analytics.</p>
          </Block>
        </div>

        <Button to="/input" variant="secondary" className="mt-8">
          <ArrowLeft className="h-4 w-4" /> Back to the calculator
        </Button>
        </div>
      </Section>
    </div>
  )
}
