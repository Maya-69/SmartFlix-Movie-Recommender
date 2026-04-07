import { useEffect, useState } from 'react'

const initialFormState = {
  watched: true,
  watch_duration: '30',
  completed: false,
  skipped_scenes: false,
  skipped_music: false,
  interest_level: 3,
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
        watched: formState.watched,
        watch_duration: formState.watch_duration,
        completed: formState.completed,
        skipped_scenes: formState.skipped_scenes,
        skipped_music: formState.skipped_music,
        interest_level: Number(formState.interest_level),
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
        <p className="text-secondary mb-4">Logged in as <strong>{user.username}</strong>. No playback here, only structured feedback for the recommendation engine.</p>

        <form className="row g-3" onSubmit={handleSubmit}>
          <div className="col-md-6">
            <label className="form-label">Watched?</label>
            <select className="form-select" value={String(formState.watched)} onChange={(event) => updateField('watched', event.target.value === 'true')}>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </div>
          <div className="col-md-6">
            <label className="form-label">Watch duration</label>
            <select className="form-select" value={formState.watch_duration} onChange={(event) => updateField('watch_duration', event.target.value)}>
              <option value="10">10 min</option>
              <option value="30">30 min</option>
              <option value="60">60 min</option>
              <option value="full">Full</option>
            </select>
          </div>
          <div className="col-md-4">
            <div className="form-check form-switch pt-2">
              <input className="form-check-input" type="checkbox" checked={formState.completed} onChange={(event) => updateField('completed', event.target.checked)} id="completed" />
              <label className="form-check-label" htmlFor="completed">Completed in one sitting</label>
            </div>
          </div>
          <div className="col-md-4">
            <div className="form-check form-switch pt-2">
              <input className="form-check-input" type="checkbox" checked={formState.skipped_scenes} onChange={(event) => updateField('skipped_scenes', event.target.checked)} id="skippedScenes" />
              <label className="form-check-label" htmlFor="skippedScenes">Skipped scenes</label>
            </div>
          </div>
          <div className="col-md-4">
            <div className="form-check form-switch pt-2">
              <input className="form-check-input" type="checkbox" checked={formState.skipped_music} onChange={(event) => updateField('skipped_music', event.target.checked)} id="skippedMusic" />
              <label className="form-check-label" htmlFor="skippedMusic">Skipped music</label>
            </div>
          </div>
          <div className="col-12">
            <label className="form-label">Interest level</label>
            <div className="d-flex flex-wrap gap-2">
              {[1, 2, 3, 4, 5].map((level) => (
                <button key={level} type="button" className={`btn ${Number(formState.interest_level) === level ? 'btn-warning' : 'btn-outline-light'}`} onClick={() => updateField('interest_level', level)}>
                  {level}
                </button>
              ))}
            </div>
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
