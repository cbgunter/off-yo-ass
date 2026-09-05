import { type ChangeEvent, useState } from 'react'
import { api } from '@/lib/api'
import { FoodSummary } from '@/components/FoodSummary'
import { resizeImage } from '@/lib/image'

type FoodItem = { name: string; portion: string; calories: number }

type MealAnalysis = {
  items: FoodItem[]
  total_calories: number
  protein_g: number
  carbs_g: number
  fat_g: number
  confidence: 'high' | 'medium' | 'low'
  notes: string
}

type Mode = { kind: 'meal' } | null

export function Eat() {
  const [mode, setMode] = useState<Mode>(null)
  const [mealDescription, setMealDescription] = useState('')
  const [mealPhotoBase64, setMealPhotoBase64] = useState<string | null>(null)
  const [mealPhotoPreview, setMealPhotoPreview] = useState<string | null>(null)
  const [mealPhotoId, setMealPhotoId] = useState<string | null>(null)
  const [mealAnalysis, setMealAnalysis] = useState<MealAnalysis | null>(null)
  const [mealBusy, setMealBusy] = useState(false)
  const [saved, setSaved] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const reset = () => {
    setMode(null)
    setMealDescription('')
    setMealPhotoBase64(null)
    setMealPhotoPreview(null)
    setMealPhotoId(null)
    setMealAnalysis(null)
  }

  const openMode = (next: Mode) => {
    setSaved(null)
    setError(null)
    setMode(next)
  }

  const onMealPhotoChange = async (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const { base64, dataUrl } = await resizeImage(file)
      setMealPhotoBase64(base64)
      setMealPhotoPreview(dataUrl)
    } catch {
      setError('Could not read that photo. Try again.')
    }
  }

  const analyzeMeal = async () => {
    if (!mealPhotoBase64 && !mealDescription.trim()) {
      setError('Add a photo or a description.')
      return
    }
    setError(null)
    setMealBusy(true)
    try {
      const res = await api.post<{ photo_id: string | null; analysis: MealAnalysis }>(
        '/meals/analyze',
        { photo_base64: mealPhotoBase64, description: mealDescription },
      )
      setMealPhotoId(res.photo_id)
      setMealAnalysis(res.analysis)
    } catch {
      setError('Could not analyze that meal. Try again.')
    } finally {
      setMealBusy(false)
    }
  }

  const saveMeal = async () => {
    if (!mealAnalysis) return
    setError(null)
    setMealBusy(true)
    try {
      await api.post('/meals', {
        photo_id: mealPhotoId,
        description: mealDescription,
        analysis: mealAnalysis,
      })
      setSaved('Meal logged.')
      reset()
      // FoodSummary fetches on mount only -- bump its key so it re-fetches
      // and shows the meal that was just saved without a page reload.
      setRefreshKey((k) => k + 1)
    } catch {
      setError('Could not save. Try again.')
    } finally {
      setMealBusy(false)
    }
  }

  return (
    <div className="screen">
      <h1 className="screen-title">Eat</h1>

      {saved && !mode && <p className="body-text">{saved}</p>}

      {!mode && (
        <div className="stack">
          <button className="btn btn-secondary" onClick={() => openMode({ kind: 'meal' })}>
            Log a meal
          </button>
        </div>
      )}

      {mode?.kind === 'meal' && !mealAnalysis && (
        <div className="stack">
          <div>
            <label className="field-label" htmlFor="meal-photo">
              Photo
            </label>
            <input
              id="meal-photo"
              className="input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={(e) => void onMealPhotoChange(e)}
            />
          </div>
          {mealPhotoPreview && (
            <img src={mealPhotoPreview} alt="" className="meal-photo-preview" />
          )}
          <div>
            <label className="field-label" htmlFor="meal-description">
              Description
            </label>
            <textarea
              id="meal-description"
              className="input"
              style={{ minHeight: '72px', paddingTop: 'var(--space-3)' }}
              value={mealDescription}
              onChange={(e) => setMealDescription(e.target.value)}
              placeholder="Grilled chicken, rice, side salad"
            />
          </div>
          <div className="btn-row">
            <button className="btn btn-secondary" onClick={reset}>
              Cancel
            </button>
            <button className="btn btn-primary" disabled={mealBusy} onClick={() => void analyzeMeal()}>
              {mealBusy ? 'Analyzing…' : 'Analyze'}
            </button>
          </div>
          {error && <p className="empty-state">{error}</p>}
        </div>
      )}

      {mode?.kind === 'meal' && mealAnalysis && (
        <div className="stack">
          {mealPhotoPreview && (
            <img src={mealPhotoPreview} alt="" className="meal-photo-preview" />
          )}
          <div>
            <span className="metric-label">Estimate</span>
            <div className="metric-value">
              {mealAnalysis.total_calories}
              <span className="timestamp"> cal</span>
            </div>
            <p className="timestamp">
              {mealAnalysis.protein_g.toFixed(0)}g protein, {mealAnalysis.carbs_g.toFixed(0)}g
              carbs, {mealAnalysis.fat_g.toFixed(0)}g fat
            </p>
          </div>
          <div>
            {mealAnalysis.items.map((item, i) => (
              <div key={`${item.name}-${i}`} className="food-item-row">
                <span className="body-text">
                  {item.name}, {item.portion}
                </span>
                <span className="timestamp">{item.calories} cal</span>
              </div>
            ))}
          </div>
          {mealAnalysis.confidence !== 'high' && (
            <p className="empty-state">Confidence: {mealAnalysis.confidence}.</p>
          )}
          {mealAnalysis.notes && <p className="timestamp">{mealAnalysis.notes}</p>}
          <div className="btn-row">
            <button className="btn btn-secondary" onClick={() => setMealAnalysis(null)}>
              Add detail
            </button>
            <button className="btn btn-primary" disabled={mealBusy} onClick={() => void saveMeal()}>
              {mealBusy ? 'Saving…' : 'Save'}
            </button>
          </div>
          {error && <p className="empty-state">{error}</p>}
        </div>
      )}

      <hr className="hairline" />
      <FoodSummary key={refreshKey} />
    </div>
  )
}
