// Minimal ambient types for the Google Identity Services script
// (https://accounts.google.com/gsi/client), loaded at runtime in
// GoogleSignInButton — not published on npm, so declared by hand.

interface GoogleIdCredentialResponse {
  credential: string
  select_by?: string
}

interface GoogleIdConfig {
  client_id: string
  callback: (response: GoogleIdCredentialResponse) => void
  auto_select?: boolean
  itp_support?: boolean
}

interface GoogleIdButtonConfig {
  type?: 'standard' | 'icon'
  theme?: 'outline' | 'filled_blue' | 'filled_black'
  size?: 'large' | 'medium' | 'small'
  text?: 'signin_with' | 'signup_with' | 'continue_with' | 'signin'
  shape?: 'rectangular' | 'pill' | 'circle' | 'square'
  logo_alignment?: 'left' | 'center'
  width?: number
}

interface Window {
  google?: {
    accounts: {
      id: {
        initialize: (config: GoogleIdConfig) => void
        renderButton: (parent: HTMLElement, options: GoogleIdButtonConfig) => void
        prompt: () => void
      }
    }
  }
}
