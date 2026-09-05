import { useEffect, useState } from 'react'
import { api } from '@/lib/api'

type QuestionData = {
  question: string
  week_ending: string
  answered: boolean
}

export function Question() {
  const [data, setData] = useState<QuestionData | null | undefined>(undefined)
  const [error, setError] = useState(false)
  const [answer, setAnswer] = useState('')
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    api
      .get<QuestionData | null>('/question/latest')
      .then(setData)
      .catch(() => setError(true))
  }, [])

  const submit = async () => {
    if (!answer.trim()) return
    await api.post('/question/answer', { text: answer })
    setSubmitted(true)
  }

  return (
    <div className="screen">
      <h1 className="screen-title">This week's question</h1>

      {error && <p className="empty-state">Could not load this week's question.</p>}
      {data === undefined && !error && <p className="empty-state">Loading.</p>}
      {data === null && <p className="empty-state">No question yet. Check back Sunday evening.</p>}

      {data && (
        <div className="stack">
          <p className="body-text">{data.question}</p>

          {(data.answered || submitted) && <p className="timestamp">Answered.</p>}

          {!data.answered && !submitted && (
            <div className="stack">
              <textarea
                className="input"
                style={{ minHeight: '96px', paddingTop: 'var(--space-3)' }}
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type an answer."
              />
              <button className="btn btn-primary" onClick={() => void submit()}>
                Send
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
