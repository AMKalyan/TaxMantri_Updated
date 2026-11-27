import { ArrowRight } from 'lucide-react'
import { Button, Eyebrow, Section } from '../components/ui'
import amkImg from '../images/amk.webp'
import chiruImg from '../images/chiru.webp'
import srikanthImg from '../images/srikanth.webp'
import rishiImg from '../images/rishi.webp'

const teamMembers = [
  { name: 'amk', role: 'Co-Founder & Developer', image: amkImg },
  { name: 'chiru', role: 'Co-Founder & Developer', image: chiruImg },
  { name: 'srikanth', role: 'Co-Founder & Developer', image: srikanthImg },
  { name: 'rishi', role: 'Co-Founder & Developer', image: rishiImg },
]

export default function AboutPage() {
  return (
    <div className="bg-white">
      <div className="border-b border-line bg-gradient-to-b from-brand-50/60 to-white">
        <Section className="py-12 sm:py-16">
          <Eyebrow>About</Eyebrow>
          <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">
            The team behind TaxMantri
          </h1>
          <p className="mt-4 max-w-2xl text-lg leading-relaxed text-muted">
            We're on a mission to simplify tax filing for every salaried employee in India using smart,
            deterministic rule engines.
          </p>
        </Section>
      </div>

      <Section className="py-12 sm:py-16">
        <ul className="grid grid-cols-2 gap-4 sm:gap-6 md:grid-cols-4">
          {teamMembers.map((member) => (
            <li key={member.name}>
              <img
                src={member.image}
                alt={member.name}
                loading="lazy"
                width="400"
                height="400"
                className="aspect-square w-full rounded-2xl border border-line object-cover"
              />
              <h3 className="mt-3 font-semibold capitalize text-ink">{member.name}</h3>
              <p className="text-sm text-muted">{member.role}</p>
            </li>
          ))}
        </ul>

        <div className="mt-14 flex flex-col items-start gap-4 rounded-2xl border border-line bg-surface p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
          <p className="text-lg font-semibold text-ink">See what TaxMantri finds for your salary.</p>
          <Button to="/input" className="w-full sm:w-auto">
            Calculate my tax <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </Section>
    </div>
  )
}
