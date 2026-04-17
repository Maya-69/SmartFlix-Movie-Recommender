import { useEffect, useState } from 'react'

const initialFormState = {
  rating: 3,
  watch_duration_minutes: 30,
  percent_completed: '',
  watched_one_sitting: false,
  skip_count: 0,
  would_watch_again: false,
  time_of_day: 'night',
}

function MovieInteractionModal({ movie, user, onClose, onSubmit, saving }) {
  const [formState, setFormState] = useState(initialFormState)
  const [localError, setLocalError] = useState('')

  useEffect(() => {
    setFormState(initialFormState)
    setLocalError('')
  }, [movie])

  if (!movie) {
    return null
  }

  const updateField = (field, value) => {
    setFormState((current) => ({
      ...current,
      [field]: value,
    }))
  }

  const handleSubmit = async (event) => {
    event.preventDefault()
    setLocalError('')

    try {
      await onSubmit({
        rating: Number(formState.rating),
        watch_duration_minutes: formState.watch_duration_minutes === '' ? null : Number(formState.watch_duration_minutes),
        percent_completed: formState.percent_completed === '' ? null : Number(formState.percent_completed),
        watched_one_sitting: formState.watched_one_sitting,
        skip_count: Number(formState.skip_count),
        would_watch_again: formState.would_watch_again,
        time_of_day: formState.time_of_day,
      })
    } catch (error) {
      setLocalError(error.message)
    }
  }

  return (
    <div className="modal-shell" role="dialog" aria-modal="true" aria-labelledby="interaction-title">
      <div className="modal-card glass-card">
        <div className="modal-header border-0 pb-2">
          <div>
            <p className="eyebrow mb-1">Capture interaction</p>
            <h4 id="interaction-title" className="mb-0">{movie.title}</h4>
          </div>
          <button type="button" className="btn-close btn-close-white" aria-label="Close" onClick={onClose} />
        </div>
        <p className="text-secondary mb-4">Logged in as <strong>{user.username}</strong>. No playback here, only structured feedback stored in your local app database.</p>

        <form className="row g-3" onSubmit={handleSubmit}>
          <div className="col-md-4">
            <label className="form-label">Rating (1-5)</label>
            <select className="form-select" value={String(formState.rating)} onChange={(event) => updateField('rating', Number(event.target.value))}>
              <option value="1">1</option>
              <option value="2">2</option>
              <option value="3">3</option>
              <option value="4">4</option>
              <option value="5">5</option>
            </select>
          </div>
          <div className="col-md-4">
            <label className="form-label">Watch duration (minutes)</label>
            <input
              className="form-control"
              type="number"
              min="0"
              value={formState.watch_duration_minutes}
              onChange={(event) => updateField('watch_duration_minutes', event.target.value === '' ? '' : Number(event.target.value))}
              placeholder="e.g. 45"
            />
          </div>
          <div className="col-md-4">
            <label className="form-label">% completed (optional)</label>
            <input
              className="form-control"
              type="number"
              min="0"
              max="100"
              value={formState.percent_completed}
              onChange={(event) => updateField('percent_completed', event.target.value === '' ? '' : Number(event.target.value))}
              placeholder="0-100"
            />
          </div>
          <div className="col-md-4">
            <div className="form-check form-switch pt-2">
              <input className="form-check-input" type="checkbox" checked={formState.watched_one_sitting} onChange={(event) => updateField('watched_one_sitting', event.target.checked)} id="watchedOneSitting" />
              <label className="form-check-label" htmlFor="watchedOneSitting">Watched in one sitting</label>
            </div>
          </div>
          <div className="col-md-4">
            <label className="form-label">Number of skips</label>
            <input
              className="form-control"
              type="number"
              min="0"
              value={formState.skip_count}
              onChange={(event) => updateField('skip_count', event.target.value === '' ? 0 : Number(event.target.value))}
            />
          </div>
          <div className="col-md-4">
            <div className="form-check form-switch pt-2">
              <input className="form-check-input" type="checkbox" checked={formState.would_watch_again} onChange={(event) => updateField('would_watch_again', event.target.checked)} id="wouldWatchAgain" />
              <label className="form-check-label" htmlFor="wouldWatchAgain">Would watch again</label>
            </div>
          </div>
          <div className="col-12">
            <label className="form-label">Time of day</label>
            <select className="form-select" value={formState.time_of_day} onChange={(event) => updateField('time_of_day', event.target.value)}>
              <option value="morning">Morning</option>
              <option value="afternoon">Afternoon</option>
              <option value="night">Night</option>
            </select>
          </div>

          {localError ? <div className="col-12"><div className="alert alert-danger mb-0">{localError}</div></div> : null}

          <div className="col-12 d-flex justify-content-end gap-2 pt-2">
            <button type="button" className="btn btn-outline-light" onClick={onClose}>Cancel</button>
            <button className="btn btn-primary" type="submit" disabled={saving}>
              {saving ? 'Saving...' : 'Save interaction'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default MovieInteractionModal
