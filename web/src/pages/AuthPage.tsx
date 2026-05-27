import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google'
import { Alert, AlertDescription } from '@/components/ui/alert'
import {
  isLoggedIn,
  setSession,
  setStoredApiKey,
  getGoogleConfig,
  googleLogin,
  type AuthResponse,
} from '@/lib/api'
import { Sun, Moon } from 'lucide-react'
import { useTheme } from '@/lib/theme'

export function AuthPage() {
  const navigate = useNavigate()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleClientId, setGoogleClientId] = useState('')

  useEffect(() => {
    getGoogleConfig()
      .then((res) => setGoogleClientId(res.client_id))
      .catch(() => {})
  }, [])

  const { resolved, setTheme } = useTheme()

  if (isLoggedIn()) {
    navigate('/dashboard', { replace: true })
    return null
  }

  function handleAuthSuccess(res: AuthResponse) {
    setSession(res.session_token)
    setStoredApiKey(res.api_key)
    localStorage.setItem(
      'anytool_user',
      JSON.stringify({ name: res.name, email: res.email, picture: res.picture }),
    )
    navigate('/dashboard')
  }

  async function handleGoogleSuccess(credentialResponse: { credential?: string }) {
    if (!credentialResponse.credential) {
      setError('No credential from Google')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await googleLogin(credentialResponse.credential)
      handleAuthSuccess(res)
    } catch (err: unknown) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen">
      {/* Left — Auth form */}
      <div className="flex w-full flex-col justify-center px-8 lg:w-1/2 lg:px-20 xl:px-32">
        <div className="mx-auto w-full max-w-sm">
          {/* Logo */}
          <div className="mb-2 flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
              AT
            </div>
            <span className="text-xl font-semibold tracking-tight">anytool</span>
          </div>

          <p className="mb-8 text-sm text-muted-foreground">
            Sign in with your Google account to get started.
          </p>

          {/* Error */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Google SSO */}
          {googleClientId ? (
            <GoogleOAuthProvider clientId={googleClientId}>
              <div className="flex flex-col gap-3">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError('Google sign-in failed')}
                  theme={resolved === 'dark' ? 'filled_black' : 'outline'}
                  size="large"
                  width="100%"
                  text="continue_with"
                />
              </div>
            </GoogleOAuthProvider>
          ) : (
            <div className="flex items-center justify-center rounded-lg border border-dashed p-6">
              <p className="text-sm text-muted-foreground">
                {loading ? 'Loading...' : 'Google sign-in is not configured. Contact your admin.'}
              </p>
            </div>
          )}

          <p className="mt-6 text-center text-xs text-muted-foreground">
            By signing in, you agree to our terms of service and privacy policy.
          </p>
        </div>
      </div>

      {/* Right — Branding panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-muted/40 flex-col items-center justify-center p-12 relative">
        {/* Theme toggle */}
        <button
          onClick={() => setTheme(resolved === 'dark' ? 'light' : 'dark')}
          className="absolute top-4 right-4 p-2 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
        >
          {resolved === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
        <div className="max-w-md text-center">
          <blockquote className="text-2xl font-medium leading-relaxed text-foreground">
            &ldquo;One API key. 98 actions across 8 apps. No more wrestling with OAuth flows and broken SDK wrappers.&rdquo;
          </blockquote>

          <div className="mt-8 flex items-center justify-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-full bg-primary text-primary-foreground text-sm font-bold">
              AT
            </div>
            <div className="text-left">
              <p className="text-sm font-medium">anytool</p>
              <p className="text-xs text-muted-foreground">
                Agent-native API integrations
              </p>
            </div>
          </div>

          {/* Stats */}
          <div className="mt-12 grid grid-cols-3 gap-6">
            <div>
              <p className="text-3xl font-bold">98</p>
              <p className="text-xs text-muted-foreground mt-1">API Actions</p>
            </div>
            <div>
              <p className="text-3xl font-bold">8</p>
              <p className="text-xs text-muted-foreground mt-1">Apps</p>
            </div>
            <div>
              <p className="text-3xl font-bold">0</p>
              <p className="text-xs text-muted-foreground mt-1">Wrappers</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
