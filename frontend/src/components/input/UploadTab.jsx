import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, FileText, CheckCircle, AlertCircle } from 'lucide-react'
import toast from 'react-hot-toast'
import { uploadForm16, confirmProfile, calculateTax } from '../../api/endpoints.js'
import OCRFieldReview from './OCRFieldReview.jsx'
import ErrorBanner from '../common/ErrorBanner.jsx'
import { Badge, Button, Card } from '../ui'

const FIELD_CLASS =
  'w-full min-h-[44px] rounded-xl border border-line bg-white pr-3.5 py-2.5 text-base text-ink transition-colors hover:border-slate-300 focus:border-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500/30 sm:text-sm'

const REQUIRED_EXTRA_FIELDS = ['monthly_rent_paid', 'city_type', 'age_bracket']

/**
 * Props:
 *   onCalculationComplete (fn) — called with (profileId, taxResult) after full flow
 *   onCalculating (fn)         — called with bool to show/hide loading overlay
 */
export default function UploadTab({ onCalculationComplete, onCalculating }) {
  const [phase, setPhase] = useState('idle') // idle | uploading | review | confirming
  const [sessionId, setSessionId] = useState(null)
  const [extractedFields, setExtractedFields] = useState({})
  const [ocrSummary, setOcrSummary] = useState(null)
  const [fieldEdits, setFieldEdits] = useState({})
  const [extraFields, setExtraFields] = useState({
    monthly_rent_paid: '',
    city_type: 'metro',
    age_bracket: 'under60',
    parent_senior_citizen: false,
  })
  const [error, setError] = useState(null)

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    setError(null)
    setPhase('uploading')

    try {
      const result = await uploadForm16(file)
      setFieldEdits({})
      setSessionId(result.session_id)
      setExtractedFields(result.extracted_fields ?? {})
      setOcrSummary(result.summary)
      setPhase('review')
      toast.success(`Extracted ${result.summary?.green_count ?? 0} fields automatically.`)
    } catch (err) {
      setPhase('idle')
      setError(err?.response?.data ?? 'OCR extraction failed. Please try again.')
    }
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'image/jpeg': ['.jpg', '.jpeg'],
      'image/png': ['.png'],
    },
    maxSize: 5 * 1024 * 1024,
    multiple: false,
    onDropRejected: (files) => {
      const err = files[0]?.errors?.[0]
      if (err?.code === 'file-too-large') toast.error('File exceeds 5 MB limit.')
      else if (err?.code === 'file-invalid-type') toast.error('Only PDF, JPEG, PNG allowed.')
      else toast.error('Invalid file.')
    },
  })

  const handleConfirm = async () => {
    // Validate extra fields
    if (!extraFields.city_type) {
      toast.error('Please select your city type.')
      return
    }
    if (!extraFields.age_bracket) {
      toast.error('Please select your age bracket.')
      return
    }

    setError(null)
    setPhase('confirming')
    onCalculating?.(true)

    try {
      // Merge OCR edits with extra fields
      const editedFields = {
        ...Object.fromEntries(Object.entries(fieldEdits).filter(([, v]) => v !== '' && v != null)),
        monthly_rent_paid: Number(extraFields.monthly_rent_paid) || 0,
        city_type: extraFields.city_type,
        age_bracket: extraFields.age_bracket,
        parent_senior_citizen: extraFields.parent_senior_citizen,
        input_method: 'ocr',
      }

      const confirmResult = await confirmProfile({ session_id: sessionId, edited_fields: editedFields })
      const profileId = confirmResult.profile_id

      const taxResult = await calculateTax(profileId)
      onCalculationComplete?.(profileId, taxResult)
    } catch (err) {
      setPhase('review')
      onCalculating?.(false)
      setError(err?.response?.data ?? 'Confirmation failed. Please try again.')
    }
  }


  return (
    <div>
      <ErrorBanner error={error} onDismiss={() => setError(null)} />

      <AnimatePresence mode="wait">
        {phase === 'idle' || phase === 'uploading' ? (
          <motion.div
            key="dropzone"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <div
              {...getRootProps()}
              className={[
                'flex min-h-[240px] cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-5 py-10 text-center transition-colors sm:p-12',
                'focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2',
                isDragActive
                  ? 'border-brand-500 bg-brand-50'
                  : 'border-line bg-surface hover:border-brand-200 hover:bg-brand-50/40',
                phase === 'uploading' ? 'pointer-events-none opacity-70' : '',
              ].join(' ')}
            >
              <input {...getInputProps()} />
              {phase === 'uploading' ? (
                <div className="flex flex-col items-center gap-3" role="status">
                  <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-600" />
                  <p className="font-semibold text-ink">Uploading & extracting…</p>
                  <p className="text-sm text-subtle">This may take 10–30 seconds</p>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-4">
                  <div className={[
                    'flex h-14 w-14 items-center justify-center rounded-2xl border transition-colors',
                    isDragActive ? 'border-brand-200 bg-white' : 'border-line bg-white shadow-card',
                  ].join(' ')}>
                    {isDragActive ? (
                      <FileText className="h-7 w-7 text-brand-600" aria-hidden="true" />
                    ) : (
                      <Upload className="h-7 w-7 text-brand-600" aria-hidden="true" />
                    )}
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-ink">
                      {isDragActive ? 'Drop it here!' : 'Upload Form 16'}
                    </p>
                    <p className="mt-1 text-sm text-muted">
                      Drag & drop or <span className="font-semibold text-brand-700">click to browse</span>
                    </p>
                    <p className="mt-2 text-xs text-subtle">PDF, JPEG, PNG · Max 5 MB</p>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="review"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
          >
            {/* Summary chips */}
            {ocrSummary && (
              <div className="mb-4 flex flex-wrap gap-2">
                {ocrSummary.green_count > 0 && (
                  <Badge tone="brand">
                    <CheckCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    {ocrSummary.green_count} auto-filled
                  </Badge>
                )}
                {ocrSummary.yellow_count > 0 && (
                  <Badge tone="warning">
                    <AlertCircle className="h-3.5 w-3.5" aria-hidden="true" />
                    {ocrSummary.yellow_count} to review
                  </Badge>
                )}
                {ocrSummary.red_count > 0 && (
                  <Badge tone="neutral">
                    {ocrSummary.red_count} not extracted
                  </Badge>
                )}
              </div>
            )}

            {/* OCR field review */}
            <Card className="p-4 sm:p-5">
              <h3 className="mb-4 text-sm font-semibold text-ink">Extracted from Form 16</h3>
              <OCRFieldReview
                extractedFields={extractedFields}
                onChange={(edits) => setFieldEdits(edits)}
              />
            </Card>

            {/* Extra fields not in Form 16 */}
            <Card className="mt-4 p-4 sm:p-5">
              <h3 className="mb-4 text-sm font-semibold text-ink">
                Additional details (not on Form 16)
              </h3>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="upload_monthly_rent" className="text-sm font-medium text-ink">
                    Monthly Rent Paid (₹)
                  </label>
                  <div className="relative">
                    <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 select-none text-sm font-medium text-subtle">₹</span>
                    <input
                      id="upload_monthly_rent"
                      type="number"
                      inputMode="numeric"
                      min={0}
                      value={extraFields.monthly_rent_paid}
                      onChange={(e) => setExtraFields(prev => ({ ...prev, monthly_rent_paid: e.target.value }))}
                      className={`${FIELD_CLASS} tabular pl-8`}
                      placeholder="0"
                    />
                  </div>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="upload_city_type" className="text-sm font-medium text-ink">City Type <span className="text-red-600">*</span></label>
                  <select
                    id="upload_city_type"
                    value={extraFields.city_type}
                    onChange={(e) => setExtraFields(prev => ({ ...prev, city_type: e.target.value }))}
                    className={`${FIELD_CLASS} pl-3.5`}
                  >
                    <option value="metro">Metro (Mumbai, Delhi, Chennai, Kolkata)</option>
                    <option value="non_metro">Non-Metro</option>
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label htmlFor="upload_age_bracket" className="text-sm font-medium text-ink">Age Bracket <span className="text-red-600">*</span></label>
                  <select
                    id="upload_age_bracket"
                    value={extraFields.age_bracket}
                    onChange={(e) => setExtraFields(prev => ({ ...prev, age_bracket: e.target.value }))}
                    className={`${FIELD_CLASS} pl-3.5`}
                  >
                    <option value="under60">Under 60</option>
                    <option value="60_79">60–79 (Senior Citizen)</option>
                    <option value="80plus">80+ (Super Senior Citizen)</option>
                  </select>
                </div>
                <div className="flex items-end">
                  <label
                    htmlFor="upload_parent_sc"
                    className="flex min-h-[44px] w-full cursor-pointer items-center gap-3 rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink"
                  >
                    <input
                      type="checkbox"
                      id="upload_parent_sc"
                      checked={extraFields.parent_senior_citizen}
                      onChange={(e) => setExtraFields(prev => ({ ...prev, parent_senior_citizen: e.target.checked }))}
                      className="h-4 w-4 shrink-0 rounded accent-brand-600"
                    />
                    Parents are senior citizens (60+)
                  </label>
                </div>
              </div>
            </Card>

            <div className="mt-6 flex flex-col-reverse gap-3 sm:flex-row">
              <Button
                variant="secondary"
                onClick={() => { setPhase('idle'); setExtractedFields({}); setSessionId(null); setFieldEdits({}); setOcrSummary(null) }}
                className="w-full sm:w-auto"
              >
                Re-upload
              </Button>
              <Button
                onClick={handleConfirm}
                disabled={phase === 'confirming'}
                className="w-full sm:flex-1"
              >
                {phase === 'confirming' ? 'Confirming…' : 'Confirm & Analyse Tax'}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
