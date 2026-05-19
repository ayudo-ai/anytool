import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { signup, setApiKey, hasApiKey } from '@/lib/api'
import { Copy, Check, ArrowRight } from 'lucide-react'

export function AuthPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'login' | 'signup'>(hasApiKey() ? 'login' : 'signup')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [apiKey, setApiKeyInput] = useState('')
  const [createdKey, setCreatedKey] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  // If already has key, go to dashboard
  if (hasApiKey() && !createdKey) {
    navigate('/dashboard', { replace: true })
    return null
  }

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await signup(name, email)
      setCreatedKey(res.api_key)
      setApiKey(res.api_key)
    } catch (err: unknown) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  function handleLogin(e: React.FormEvent) {
    e.preventDefault()
    if (!apiKey.startsWith('at_')) {
      setError('API key must start with at_')
      return
    }
    setApiKey(apiKey)
    navigate('/dashboard')
  }

  function handleCopy() {
    navigator.clipboard.writeText(createdKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Show key after signup
  if (createdKey) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Your API Key</CardTitle>
            <CardDescription>
              Store this key securely — it won't be shown again.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 rounded-md border bg-muted p-3">
              <code className="flex-1 text-sm break-all font-mono">
                {createdKey}
              </code>
              <Button variant="ghost" size="sm" onClick={handleCopy}>
                {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
              </Button>
            </div>
          </CardContent>
          <CardFooter>
            <Button className="w-full" onClick={() => navigate('/dashboard')}>
              Go to Dashboard
              <ArrowRight className="ml-2 size-4" />
            </Button>
          </CardFooter>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto mb-2 flex size-10 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold">
            AT
          </div>
          <CardTitle className="text-xl">
            {mode === 'signup' ? 'Create your account' : 'Sign in'}
          </CardTitle>
          <CardDescription>
            {mode === 'signup'
              ? 'Get your API key and start integrating.'
              : 'Enter your API key to access the dashboard.'}
          </CardDescription>
        </CardHeader>

        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {mode === 'signup' ? (
            <form onSubmit={handleSignup} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  placeholder="Acme Corp"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="dev@acme.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" disabled={loading} className="w-full">
                {loading ? 'Creating...' : 'Create Account'}
              </Button>
            </form>
          ) : (
            <form onSubmit={handleLogin} className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <Label htmlFor="key">API Key</Label>
                <Input
                  id="key"
                  placeholder="at_xxxx..."
                  value={apiKey}
                  onChange={(e) => setApiKeyInput(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full">
                Sign In
              </Button>
            </form>
          )}
        </CardContent>

        <CardFooter className="justify-center">
          <Button
            variant="link"
            size="sm"
            onClick={() => {
              setMode(mode === 'signup' ? 'login' : 'signup')
              setError('')
            }}
          >
            {mode === 'signup'
              ? 'Already have an API key? Sign in'
              : "Don't have a key? Create account"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  )
}
