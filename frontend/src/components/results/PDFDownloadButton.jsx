import { useState } from 'react'
import { Download, Loader2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { exportPDF } from '../../api/endpoints.js'
import { Button } from '../ui/index.jsx'

// Downloads the PDF report for profileId.
export default function PDFDownloadButton({ profileId }) {
  const [loading, setLoading] = useState(false)

  const handleDownload = async () => {
    if (!profileId || loading) return

    setLoading(true)
    try {
      const blob = await exportPDF(profileId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `TaxMantri_AY2026-27_${profileId.slice(0, 8)}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      toast.success('PDF downloaded!')
    } catch {
      toast.error('PDF generation failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Button size="sm" onClick={handleDownload} disabled={loading || !profileId}>
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" />
      ) : (
        <Download className="h-4 w-4" />
      )}
      {loading ? 'Generating PDF…' : 'Download PDF Report'}
    </Button>
  )
}
