import { Loader2 } from 'lucide-react'

export function StatusBar({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground/70 bg-muted/40 rounded-lg border border-border/30 font-medium">
      <Loader2 className="h-3 w-3 animate-spin text-primary/50" strokeWidth={2} />
      {message}
    </div>
  )
}
