import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
import HeroPage from './pages/HeroPage.jsx'
import InputPage from './pages/InputPage.jsx'
import ResultsPage from './pages/ResultsPage.jsx'
import HowItWorksPage from './pages/HowItWorksPage.jsx'
import AboutPage from './pages/AboutPage.jsx'
import PrivacyPage from './pages/PrivacyPage.jsx'
import ChatWidget from './components/common/ChatWidget.jsx'
import ServerWakeBanner from './components/common/ServerWakeBanner.jsx'
import Navbar from './components/Navbar.jsx'
import { Footer } from './components/ui'

function ScrollToTop() {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return null
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <ServerWakeBanner />
      <div className="flex min-h-screen flex-col">
        <Navbar />
        <div className="flex-1">
          <Routes>
            <Route path="/" element={<HeroPage />} />
            <Route path="/how-it-works" element={<HowItWorksPage />} />
            <Route path="/about" element={<AboutPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/input" element={<InputPage />} />
            <Route path="/results/:profileId" element={<ResultsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        <Footer />
      </div>

      {/* Floating tax assistant, available on every page */}
      <ChatWidget />
    </>
  )
}

