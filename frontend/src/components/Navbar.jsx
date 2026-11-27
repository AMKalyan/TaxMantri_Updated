import { useState } from 'react'
import { Link, NavLink, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import logoImage from '../images/justice_scales_black_gold.png'
import PDFDownloadButton from './results/PDFDownloadButton'
import { Button } from './ui'

const LINKS = [
  { to: '/how-it-works', label: 'How it works' },
  { to: '/about', label: 'About' },
  { to: '/privacy', label: 'Privacy' },
]

export default function Navbar() {
  const location = useLocation()
  const [open, setOpen] = useState(false)
  const isResults = location.pathname.startsWith('/results')

  const linkClass = ({ isActive }) =>
    `rounded-lg px-3 py-2 text-sm font-medium transition-colors ${isActive ? 'text-ink' : 'text-muted hover:text-ink'}`

  return (
    <header className="sticky top-0 z-40 border-b border-line bg-white/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-page items-center justify-between px-4 sm:px-6">
        <Link to="/" className="flex items-center gap-2" onClick={() => setOpen(false)}>
          <img src={logoImage} alt="" className="h-8 w-auto" />
          <span className="text-lg font-bold tracking-tight text-ink">TaxMantri</span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} className={linkClass}>{l.label}</NavLink>
          ))}
          <div className="ml-3">
            {isResults
              ? <PDFDownloadButton profileId={location.pathname.split('/')[2]} />
              : <Button to="/input" size="sm">Calculate my tax</Button>}
          </div>
        </nav>

        <button
          type="button"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-ink hover:bg-surface md:hidden"
          aria-label={open ? 'Close menu' : 'Open menu'}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <nav className="border-t border-line bg-white px-4 pb-4 pt-2 md:hidden" aria-label="Mobile">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} className={linkClass} onClick={() => setOpen(false)}>
              <span className="block py-1">{l.label}</span>
            </NavLink>
          ))}
          <Button to="/input" className="mt-3 w-full" onClick={() => setOpen(false)}>Calculate my tax</Button>
        </nav>
      )}
    </header>
  )
}
