import { useEffect, useState } from 'react'

import { api } from '../api'

function Visualizations() {
  const [payload, setPayload] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const loadMetrics = async () => {
      setLoading(true)
      setError('')
      try {
        const data = await api.getNnMetrics()
        setPayload(data)
      } catch (requestError) {
        setError(requestError.message)
      } finally {
        setLoading(false)
      }
    }

    loadMetrics()
  }, [])

  const metrics = payload?.metrics || {}
  const plots = payload?.plots || {}
  const sampleRows = payload?.prediction_samples || []

  return (
    <div className="page-stack">
      <section className="hero-panel glass-card compact-hero">
        <div>
          <p className="eyebrow mb-2">Metrics</p>
          <h1 className="h2 fw-bold mb-2">Training metrics and graphs</h1>
          <p className="text-secondary mb-0">
            Loss, MAE, confusion matrix, and prediction-vs-actual visualization for the neural network stage.
          </p>
        </div>
      </section>

      {error ? <div className="alert alert-danger border-0">{error}</div> : null}

      {loading ? (
        <div className="text-center py-5 text-secondary">Building visualizations...</div>
      ) : payload ? (
        <>
          <section className="metric-grid">
            <div className="metric-card glass-card">
              <span className="metric-label">Epochs</span>
              <span className="metric-value">{metrics.epochs ?? '-'}</span>
            </div>
            <div className="metric-card glass-card">
              <span className="metric-label">Rows</span>
              <span className="metric-value">{metrics.rows ?? '-'}</span>
            </div>
            <div className="metric-card glass-card">
              <span className="metric-label">Final Loss</span>
              <span className="metric-value">{metrics.final_loss ?? '-'}</span>
            </div>
            <div className="metric-card glass-card">
              <span className="metric-label">Final MAE</span>
              <span className="metric-value">{metrics.final_mae ?? '-'}</span>
            </div>
          </section>

          <section className="graph-grid">
            <article className="graph-card glass-card">
              <h3 className="h5 mb-3">Training Loss vs Epochs</h3>
              <img className="graph-image" src={`data:image/png;base64,${plots.loss_curve}`} alt="Training loss plot" />
            </article>
            <article className="graph-card glass-card">
              <h3 className="h5 mb-3">MAE vs Epochs</h3>
              <img className="graph-image" src={`data:image/png;base64,${plots.mae_curve}`} alt="MAE plot" />
            </article>
            <article className="graph-card glass-card">
              <h3 className="h5 mb-3">Confusion Matrix</h3>
              <img className="graph-image" src={`data:image/png;base64,${plots.confusion_matrix}`} alt="Confusion matrix" />
            </article>
            <article className="graph-card glass-card">
              <h3 className="h5 mb-3">Prediction vs Actual</h3>
              <img className="graph-image" src={`data:image/png;base64,${plots.prediction_vs_actual}`} alt="Prediction versus actual plot" />
            </article>
          </section>

          <section className="glass-card p-3 p-lg-4">
            <div className="section-header mb-3">
              <div>
                <p className="eyebrow mb-1">Validation Samples</p>
                <h2 className="h4 mb-0">Rounded predictions</h2>
              </div>
            </div>
            <div className="table-responsive">
              <table className="table table-dark table-hover align-middle mb-0">
                <thead>
                  <tr>
                    <th>Actual</th>
                    <th>Predicted</th>
                  </tr>
                </thead>
                <tbody>
                  {sampleRows.slice(0, 10).map((row, index) => (
                    <tr key={`${row.actual}-${row.predicted}-${index}`}>
                      <td>{row.actual}</td>
                      <td>{row.predicted}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}

export default Visualizations
