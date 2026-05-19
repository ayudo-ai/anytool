import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Separator } from '@/components/ui/separator'
import {
  isLoggedIn,
  setSession,
  setStoredApiKey,
  getGoogleConfig,
  googleLogin,
  emailSignup,
  emailLogin,
  type AuthResponse,
} from '@/lib/api'
import { Eye, EyeOff } from 'lucide-react'

export function AuthPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'signup' | 'login'>('signup')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleClientId, setGoogleClientId] = useState('')

  useEffect(() => {
    getGoogleConfig()
      .then((res) => setGoogleClientId(res.client_id))
      .catch(() => {})
  }, [])

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

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res =
        mode === 'signup'
          ? await emailSignup(name, email, password)
          : await emailLogin(email, password)
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
          <div className="mb-8 flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground text-sm font-bold">
              AT
            </div>
            <span className="text-xl font-semibold tracking-tight">anytool</span>
          </div>

          {/* Google SSO */}
          {googleClientId && (
            <GoogleOAuthProvider clientId={googleClientId}>
              <div className="flex flex-col gap-3">
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={() => setError('Google sign-in failed')}
                  theme="outline"
                  size="large"
                  width="100%"
                  text="continue_with"
                />
              </div>

              <div className="relative my-6">
                <div className="absolute inset-0 flex items-center">
                  <Separator className="w-full" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">or</span>
                </div>
              </div>
            </GoogleOAuthProvider>
          )}

          {/* Error */}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Email form */}
          <form onSubmit={handleEmailSubmit} className="flex flex-col gap-4">
            {mode === 'signup' && (
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  placeholder="Your name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
            )}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={mode === 'signup' ? 'Min 8 characters' : 'Your password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === 'signup' ? 8 : 1}
                  className="pr-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>

            <Button type="submit" disabled={loading} className="w-full">
              {loading
                ? 'Please wait...'
                : mode === 'signup'
                  ? 'Create Account'
                  : 'Sign In'}
            </Button>
          </form>

          {/* Toggle mode */}
          <p className="mt-6 text-center text-sm text-muted-foreground">
            {mode === 'signup' ? (
              <>
                Already have an account?{' '}
                <button
                  onClick={() => { setMode('login'); setError('') }}
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                >
                  Sign in
                </button>
              </>
            ) : (
              <>
                Don&apos;t have an account?{' '}
                <button
                  onClick={() => { setMode('signup'); setError('') }}
                  className="font-medium text-foreground underline-offset-4 hover:underline"
                >
                  Create one
                </button>
              </>
            )}
          </p>
        </div>
      </div>

      {/* Right — Branding panel */}
      <div className="hidden lg:flex lg:w-1/2 bg-muted/40 flex-col items-center justify-center p-12">
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
