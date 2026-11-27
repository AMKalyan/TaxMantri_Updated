import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Trash2 } from 'lucide-react'
import toast from 'react-hot-toast'
import { deleteMyData } from '../../api/endpoints.js'
import { Button } from '../ui/index.jsx'

/** Deletes everything stored for this profile and chat session, then clears local state. */
export default function DeleteDataButton({ profileId }) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)

  const onDelete = async () => {
    if (!window.confirm('Delete your salary details, results and chat history from TaxMantri? This cannot be undone.')) return
    setBusy(true)
    try {
      const sessionId = localStorage.getItem('taxmantri_chat_session')
      await deleteMyData({ profileId, sessionId })
      ;['taxmantri_profile_id', 'taxmantri_chat_session', 'taxmantri_last_form'].forEach((k) => {
        try { localStorage.removeItem(k) } catch { /* storage unavailable */ }
      })
      toast.success('Your data has been deleted.')
      navigate('/')
    } catch {
      setBusy(false)
    }
  }

  return (
    <Button variant="danger" onClick={onDelete} disabled={busy}>
      <Trash2 className="h-4 w-4" />
      {busy ? 'Deleting…' : 'Delete my data'}
    </Button>
  )
}
