import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth'
import { Nav } from '@/components/Nav'
import { SignIn } from '@/routes/SignIn'
import { Dashboard } from '@/routes/Dashboard'
import { Sources } from '@/routes/Sources'
import { Log } from '@/routes/Log'

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
            <Dashboard />
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
        path="/log"
        element={
          <Gate>
            <Log />
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
