import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { MetricRow } from '@/components/MetricRow'

type FoodItem = { name: string; portion: string; calories: number }

type Meal = {
  when: string
  description: string
  photo_id: string | null
  items: FoodItem[]
  total_calories: number
  protein_g: number
  carbs_g: number
  fat_g: number
}

type FoodTotals = {
  today: number | null
  delta: number | null
  days: number
  building: boolean
}

type TodayFood = { calories: FoodTotals; meals: Meal[] }

function signed(n: number): string {
  const sign = n > 0 ? '+' : n < 0 ? '−' : ''
  return `${sign}${Math.abs(n).toFixed(0)}`
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

function mealLabel(meal: Meal): string {
  return meal.items[0]?.name ?? (meal.description.trim() || 'Meal')
}

/**
 * Today's food, purely factual -- calories against the user's own 30-day
 * average (never a target), with no above/below color coding on the
 * delta. Coloring it would itself be a judgment about which direction is
 * "better," which is exactly what the coach's own prompt is forbidden
 * from making about food.
 */
export function FoodSummary() {
  const [data, setData] = useState<TodayFood | null>(null)

  useEffect(() => {
    api
      .get<TodayFood>('/meals/today')
      .then(setData)
      .catch(() => setData(null))
  }, [])

  if (!data) return null

  const { calories, meals } = data
  const totalProtein = meals.reduce((sum, m) => sum + m.protein_g, 0)
  const totalCarbs = meals.reduce((sum, m) => sum + m.carbs_g, 0)
  const totalFat = meals.reduce((sum, m) => sum + m.fat_g, 0)

  return (
    <div className="stack">
      <span className="metric-label">Food</span>

      {calories.building || calories.today === null ? (
        <MetricRow
          label="Calories"
          value={calories.today === null ? '—' : calories.today.toFixed(0)}
          unit="cal"
          deltaText={`building baseline, ${calories.days} of 30 days`}
        />
      ) : (
        <MetricRow
          label="Calories"
          value={calories.today.toFixed(0)}
          unit="cal"
          deltaText={`${signed(calories.delta ?? 0)} vs 30d avg`}
        />
      )}

      {meals.length > 0 && (
        <p className="timestamp">
          {totalProtein.toFixed(0)}g protein, {totalCarbs.toFixed(0)}g carbs, {totalFat.toFixed(0)}g
          fat
        </p>
      )}

      {meals.length === 0 ? (
        <p className="empty-state">No meals logged today.</p>
      ) : (
        <div>
          {meals.map((meal) => (
            <div key={meal.when} className="food-item-row">
              <div className="meal-row-main">
                {meal.photo_id && (
                  <img
                    src={`/api/meals/photo/${meal.photo_id}`}
                    alt=""
                    className="meal-thumb"
                  />
                )}
                <span className="body-text">
                  {formatTime(meal.when)}, {mealLabel(meal)}
                </span>
              </div>
              <span className="timestamp">{meal.total_calories} cal</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
