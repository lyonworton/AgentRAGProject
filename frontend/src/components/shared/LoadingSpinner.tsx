import { Loader2 } from 'lucide-react'

export function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-muted-foreground/60">
      <Loader2 className="h-7 w-7 animate-spin text-primary/40" strokeWidth={1.5} />
      <span className="text-xs font-medium text-muted-foreground/70">{text}</span>
    </div>
  )
}
