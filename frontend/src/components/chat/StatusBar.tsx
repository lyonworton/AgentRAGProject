import { Loader2 } from 'lucide-react'

export function StatusBar({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground/80 bg-muted/60 rounded-lg border border-border/40">
      <Loader2 className="h-3 w-3 animate-spin text-primary/60" />
      {message}
    </div>
  )
}
