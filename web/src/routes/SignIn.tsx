import { GoogleSignInButton } from '@/components/GoogleSignInButton'

export function SignIn() {
  return (
    <div className="screen">
      <div className="stack" style={{ marginTop: '30vh' }}>
        <h1 className="screen-title">Off yo ass</h1>
        <p className="body-text">One account. Yours.</p>
        <GoogleSignInButton />
      </div>
    </div>
  )
}
