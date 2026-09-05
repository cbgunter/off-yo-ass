import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth'
import { Nav } from '@/components/Nav'
import { SignIn } from '@/routes/SignIn'
import { Health } from '@/routes/Health'
import { Sources } from '@/routes/Sources'
import { Eat } from '@/routes/Eat'
import { TheCall } from '@/routes/TheCall'
import { Question } from '@/routes/Question'

function Gate({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    // No spinner animation, per BRANDING.md — a still, declarative wait.
    return <div className="screen empty-state">Loading.</div>
  }

  if (!user) return <Navigate to="/sign-in" replace />

  return (
    <>
      <Nav />
      {children}
    </>
  )
}

function AppRoutes() {
  const { user } = useAuth()

  return (
    <Routes>
      <Route path="/sign-in" element={user ? <Navigate to="/" replace /> : <SignIn />} />
      <Route
        path="/"
        element={
          <Gate>
            <Health />
          </Gate>
        }
      />
      <Route
        path="/sources"
        element={
          <Gate>
            <Sources />
          </Gate>
        }
      />
      <Route
        path="/eat"
        element={
          <Gate>
            <Eat />
          </Gate>
        }
      />
      <Route
        path="/call"
        element={
          <Gate>
            <TheCall />
          </Gate>
        }
      />
      <Route
        path="/question"
        element={
          <Gate>
            <Question />
          </Gate>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  )
}
