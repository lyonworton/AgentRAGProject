import { useState, useEffect, useRef } from "react"
import { useNavigate } from "react-router-dom"
import { useAuth } from "@/context/AuthContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Checkbox } from "@/components/ui/checkbox"
import { Eye, EyeOff, Sparkles } from "lucide-react"

// ── Animated Eye/Pupil components ──────────────────────────────────────────

interface PupilProps {
  size?: number; maxDistance?: number; pupilColor?: string
  forceLookX?: number; forceLookY?: number
}

function Pupil({ size = 12, maxDistance = 5, pupilColor = "black", forceLookX, forceLookY }: PupilProps) {
  const [mouseX, setMouseX] = useState(0)
  const [mouseY, setMouseY] = useState(0)
  const pupilRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { setMouseX(e.clientX); setMouseY(e.clientY) }
    window.addEventListener("mousemove", h)
    return () => window.removeEventListener("mousemove", h)
  }, [])

  const calc = () => {
    if (!pupilRef.current) return { x: 0, y: 0 }
    if (forceLookX !== undefined && forceLookY !== undefined) return { x: forceLookX, y: forceLookY }
    const r = pupilRef.current.getBoundingClientRect()
    const dx = mouseX - (r.left + r.width / 2)
    const dy = mouseY - (r.top + r.height / 2)
    const d = Math.min(Math.sqrt(dx ** 2 + dy ** 2), maxDistance)
    const a = Math.atan2(dy, dx)
    return { x: Math.cos(a) * d, y: Math.sin(a) * d }
  }

  const p = calc()
  return (
    <div ref={pupilRef} className="rounded-full" style={{
      width: size, height: size, backgroundColor: pupilColor,
      transform: `translate(${p.x}px, ${p.y}px)`, transition: 'transform 0.1s ease-out',
    }} />
  )
}

interface EyeBallProps {
  size?: number; pupilSize?: number; maxDistance?: number
  eyeColor?: string; pupilColor?: string; isBlinking?: boolean
  forceLookX?: number; forceLookY?: number
}

function EyeBall({ size = 48, pupilSize = 16, maxDistance = 10, eyeColor = "white", pupilColor = "black", isBlinking = false, forceLookX, forceLookY }: EyeBallProps) {
  const [mouseX, setMouseX] = useState(0)
  const [mouseY, setMouseY] = useState(0)
  const eyeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { setMouseX(e.clientX); setMouseY(e.clientY) }
    window.addEventListener("mousemove", h)
    return () => window.removeEventListener("mousemove", h)
  }, [])

  const calc = () => {
    if (!eyeRef.current) return { x: 0, y: 0 }
    if (forceLookX !== undefined && forceLookY !== undefined) return { x: forceLookX, y: forceLookY }
    const r = eyeRef.current.getBoundingClientRect()
    const dx = mouseX - (r.left + r.width / 2)
    const dy = mouseY - (r.top + r.height / 2)
    const d = Math.min(Math.sqrt(dx ** 2 + dy ** 2), maxDistance)
    const a = Math.atan2(dy, dx)
    return { x: Math.cos(a) * d, y: Math.sin(a) * d }
  }

  const p = calc()
  return (
    <div ref={eyeRef} className="rounded-full flex items-center justify-center transition-all duration-150" style={{
      width: size, height: isBlinking ? '2px' : size, backgroundColor: eyeColor, overflow: 'hidden',
    }}>
      {!isBlinking && (
        <div className="rounded-full" style={{
          width: pupilSize, height: pupilSize, backgroundColor: pupilColor,
          transform: `translate(${p.x}px, ${p.y}px)`, transition: 'transform 0.1s ease-out',
        }} />
      )}
    </div>
  )
}

// ── Login Page ────────────────────────────────────────────────────────────

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)

  // Character animation state
  const [mouseX, setMouseX] = useState(0)
  const [mouseY, setMouseY] = useState(0)
  const [isPurpleBlinking, setIsPurpleBlinking] = useState(false)
  const [isBlackBlinking, setIsBlackBlinking] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [isLookingAtEachOther, setIsLookingAtEachOther] = useState(false)
  const [isPurplePeeking, setIsPurplePeeking] = useState(false)
  const purpleRef = useRef<HTMLDivElement>(null)
  const blackRef = useRef<HTMLDivElement>(null)
  const yellowRef = useRef<HTMLDivElement>(null)
  const orangeRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { setMouseX(e.clientX); setMouseY(e.clientY) }
    window.addEventListener("mousemove", h)
    return () => window.removeEventListener("mousemove", h)
  }, [])

  // Purple blinking
  useEffect(() => {
    const schedule = (): (() => void) => {
      const t = setTimeout(() => {
        setIsPurpleBlinking(true)
        setTimeout(() => { setIsPurpleBlinking(false); schedule() }, 150)
      }, Math.random() * 4000 + 3000)
      return () => clearTimeout(t)
    }
    return schedule()
  }, [])

  // Black blinking
  useEffect(() => {
    const schedule = (): (() => void) => {
      const t = setTimeout(() => {
        setIsBlackBlinking(true)
        setTimeout(() => { setIsBlackBlinking(false); schedule() }, 150)
      }, Math.random() * 4000 + 3000)
      return () => clearTimeout(t)
    }
    return schedule()
  }, [])

  // Look at each other when typing
  useEffect(() => {
    if (isTyping) {
      setIsLookingAtEachOther(true)
      const t = setTimeout(() => setIsLookingAtEachOther(false), 800)
      return () => clearTimeout(t)
    }
    setIsLookingAtEachOther(false)
  }, [isTyping])

  // Purple peeking when password visible
  useEffect(() => {
    if (password.length > 0 && showPassword) {
      const schedule = (): (() => void) => {
        const t = setTimeout(() => {
          setIsPurplePeeking(true)
          setTimeout(() => { setIsPurplePeeking(false); schedule() }, 800)
        }, Math.random() * 3000 + 2000)
        return () => clearTimeout(t)
      }
      return schedule()
    }
    setIsPurplePeeking(false)
  }, [password, showPassword])

  const calcPos = (ref: React.RefObject<HTMLDivElement | null>) => {
    if (!ref.current) return { faceX: 0, faceY: 0, bodySkew: 0 }
    const r = ref.current.getBoundingClientRect()
    const cx = r.left + r.width / 2
    const cy = r.top + r.height / 3
    const dx = mouseX - cx
    const dy = mouseY - cy
    return {
      faceX: Math.max(-15, Math.min(15, dx / 20)),
      faceY: Math.max(-10, Math.min(10, dy / 30)),
      bodySkew: Math.max(-6, Math.min(6, -dx / 120)),
    }
  }

  const purplePos = calcPos(purpleRef)
  const blackPos = calcPos(blackRef)
  const yellowPos = calcPos(yellowRef)
  const orangePos = calcPos(orangeRef)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")
    setIsLoading(true)
    try {
      await login(username, password)
      navigate("/admin")
    } catch (err: any) {
      setError(err?.message || "登录失败，请检查用户名和密码")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      {/* Left: Animated Characters */}
      <div className="relative hidden lg:flex flex-col justify-between bg-gradient-to-br from-primary/90 via-primary to-primary/80 p-12 text-primary-foreground">
        <div className="relative z-20">
          <div className="flex items-center gap-2 text-lg font-semibold">
            <div className="size-8 rounded-lg bg-primary-foreground/10 backdrop-blur-sm flex items-center justify-center">
              <Sparkles className="size-4" />
            </div>
            <span>AgentRAG</span>
          </div>
        </div>

        <div className="relative z-20 flex items-end justify-center h-[400px]">
          <div className="relative" style={{ width: '440px', height: '340px' }}>
            {/* Purple character */}
            <div ref={purpleRef} className="absolute bottom-0 transition-all duration-700 ease-in-out" style={{
              left: '55px', width: '140px',
              height: (isTyping || (password.length > 0 && !showPassword)) ? '370px' : '330px',
              backgroundColor: '#6C3FF5', borderRadius: '10px 10px 0 0', zIndex: 1,
              transform: (password.length > 0 && showPassword)
                ? `skewX(0deg)`
                : (isTyping || (password.length > 0 && !showPassword))
                  ? `skewX(${(purplePos.bodySkew || 0) - 12}deg) translateX(32px)`
                  : `skewX(${purplePos.bodySkew || 0}deg)`,
              transformOrigin: 'bottom center',
            }}>
              <div className="absolute flex gap-6 transition-all duration-700 ease-in-out" style={{
                left: (password.length > 0 && showPassword) ? 16 : isLookingAtEachOther ? 44 : `${36 + purplePos.faceX}px`,
                top: (password.length > 0 && showPassword) ? 28 : isLookingAtEachOther ? 52 : `${32 + purplePos.faceY}px`,
              }}>
                <EyeBall size={15} pupilSize={6} maxDistance={4} eyeColor="white" pupilColor="#2D2D2D"
                  isBlinking={isPurpleBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -5 : isLookingAtEachOther ? 2.5 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? 0 : isLookingAtEachOther ? 3 : undefined} />
                <EyeBall size={15} pupilSize={6} maxDistance={4} eyeColor="white" pupilColor="#2D2D2D"
                  isBlinking={isPurpleBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -5 : isLookingAtEachOther ? 2.5 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? 0 : isLookingAtEachOther ? 3 : undefined} />
              </div>
            </div>

            {/* Black character */}
            <div ref={blackRef} className="absolute bottom-0 transition-all duration-700 ease-in-out" style={{
              left: '192px', width: '96px', height: '256px',
              backgroundColor: '#2D2D2D', borderRadius: '8px 8px 0 0', zIndex: 2,
              transform: (password.length > 0 && showPassword)
                ? `skewX(0deg)`
                : isLookingAtEachOther
                  ? `skewX(${(blackPos.bodySkew || 0) * 1.5 + 10}deg) translateX(16px)`
                  : (isTyping || (password.length > 0 && !showPassword))
                    ? `skewX(${(blackPos.bodySkew || 0) * 1.5}deg)`
                    : `skewX(${blackPos.bodySkew || 0}deg)`,
              transformOrigin: 'bottom center',
            }}>
              <div className="absolute flex gap-5 transition-all duration-700 ease-in-out" style={{
                left: (password.length > 0 && showPassword) ? 8 : isLookingAtEachOther ? 26 : `${21 + blackPos.faceX}px`,
                top: (password.length > 0 && showPassword) ? 22 : isLookingAtEachOther ? 10 : `${26 + blackPos.faceY}px`,
              }}>
                <EyeBall size={13} pupilSize={5} maxDistance={3} eyeColor="white" pupilColor="#2D2D2D"
                  isBlinking={isBlackBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -5 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? 0 : isLookingAtEachOther ? -3 : undefined} />
                <EyeBall size={13} pupilSize={5} maxDistance={3} eyeColor="white" pupilColor="#2D2D2D"
                  isBlinking={isBlackBlinking}
                  forceLookX={(password.length > 0 && showPassword) ? -5 : isLookingAtEachOther ? 0 : undefined}
                  forceLookY={(password.length > 0 && showPassword) ? 0 : isLookingAtEachOther ? -3 : undefined} />
              </div>
            </div>

            {/* Orange character */}
            <div ref={orangeRef} className="absolute bottom-0 transition-all duration-700 ease-in-out" style={{
              left: '0px', width: '192px', height: '160px', zIndex: 3,
              backgroundColor: '#FF9B6B', borderRadius: '96px 96px 0 0',
              transform: (password.length > 0 && showPassword) ? `skewX(0deg)` : `skewX(${orangePos.bodySkew || 0}deg)`,
              transformOrigin: 'bottom center',
            }}>
              <div className="absolute flex gap-6 transition-all duration-200 ease-out" style={{
                left: (password.length > 0 && showPassword) ? 40 : `${66 + (orangePos.faceX || 0)}px`,
                top: (password.length > 0 && showPassword) ? 68 : `${72 + (orangePos.faceY || 0)}px`,
              }}>
                <Pupil size={10} maxDistance={4} pupilColor="#2D2D2D" forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? 0 : undefined} />
                <Pupil size={10} maxDistance={4} pupilColor="#2D2D2D" forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? 0 : undefined} />
              </div>
            </div>

            {/* Yellow character */}
            <div ref={yellowRef} className="absolute bottom-0 transition-all duration-700 ease-in-out" style={{
              left: '248px', width: '112px', height: '184px',
              backgroundColor: '#E8D754', borderRadius: '56px 56px 0 0', zIndex: 4,
              transform: (password.length > 0 && showPassword) ? `skewX(0deg)` : `skewX(${yellowPos.bodySkew || 0}deg)`,
              transformOrigin: 'bottom center',
            }}>
              <div className="absolute flex gap-5 transition-all duration-200 ease-out" style={{
                left: (password.length > 0 && showPassword) ? 16 : `${42 + (yellowPos.faceX || 0)}px`,
                top: (password.length > 0 && showPassword) ? 28 : `${32 + (yellowPos.faceY || 0)}px`,
              }}>
                <Pupil size={10} maxDistance={4} pupilColor="#2D2D2D" forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? 0 : undefined} />
                <Pupil size={10} maxDistance={4} pupilColor="#2D2D2D" forceLookX={(password.length > 0 && showPassword) ? -5 : undefined} forceLookY={(password.length > 0 && showPassword) ? 0 : undefined} />
              </div>
              <div className="absolute w-16 h-[3px] bg-[#2D2D2D] rounded-full transition-all duration-200 ease-out" style={{
                left: (password.length > 0 && showPassword) ? 8 : `${32 + (yellowPos.faceX || 0)}px`,
                top: (password.length > 0 && showPassword) ? 70 : `${70 + (yellowPos.faceY || 0)}px`,
              }} />
            </div>
          </div>
        </div>

        <div className="relative z-20 flex items-center gap-8 text-sm text-primary-foreground/60">
          <span>Privacy Policy</span>
          <span>Terms of Service</span>
          <span>Contact</span>
        </div>

        <div className="absolute inset-0 bg-grid-white/[0.05] bg-[size:20px_20px]" />
        <div className="absolute top-1/4 right-1/4 size-64 bg-primary-foreground/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 left-1/4 size-96 bg-primary-foreground/5 rounded-full blur-3xl" />
      </div>

      {/* Right: Login Form */}
      <div className="flex items-center justify-center p-8 bg-background">
        <div className="w-full max-w-[420px]">
          <div className="lg:hidden flex items-center justify-center gap-2 text-lg font-semibold mb-12">
            <div className="size-8 rounded-lg bg-primary/10 flex items-center justify-center">
              <Sparkles className="size-4 text-primary" />
            </div>
            <span>AgentRAG</span>
          </div>

          <div className="text-center mb-10">
            <h1 className="text-3xl font-bold tracking-tight mb-2">Welcome back!</h1>
            <p className="text-muted-foreground text-sm">Please enter your details</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-sm font-medium">Username</Label>
              <Input id="username" placeholder="admin"
                value={username} autoComplete="off"
                onChange={(e) => setUsername(e.target.value)}
                onFocus={() => setIsTyping(true)}
                onBlur={() => setIsTyping(false)}
                required className="h-12 bg-background border-border/60 focus:border-primary" />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">Password</Label>
              <div className="relative">
                <Input id="password" type={showPassword ? "text" : "password"} placeholder="••••••••"
                  value={password} onChange={(e) => setPassword(e.target.value)}
                  required className="h-12 pr-10 bg-background border-border/60 focus:border-primary" />
                <button type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                  {showPassword ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Checkbox id="remember" />
                <Label htmlFor="remember" className="text-sm font-normal cursor-pointer">Remember for 30 days</Label>
              </div>
              <a href="#" className="text-sm text-primary hover:underline font-medium">Forgot password?</a>
            </div>

            {error && (
              <div className="p-3 text-sm text-red-400 bg-red-950/20 border border-red-900/30 rounded-lg">{error}</div>
            )}

            <Button type="submit" className="w-full h-12 text-base font-medium" size="lg" disabled={isLoading}>
              {isLoading ? "Signing in..." : "Log in"}
            </Button>
          </form>

          <div className="text-center text-sm text-muted-foreground mt-8">
            Don't have an account?{" "}
            <a href="#" className="text-foreground font-medium hover:underline">Contact Admin</a>
          </div>
        </div>
      </div>
    </div>
  )
}