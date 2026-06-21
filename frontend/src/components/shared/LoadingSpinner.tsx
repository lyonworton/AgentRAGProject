import { Loader2 } from 'lucide-react'

export function LoadingSpinner({ text = 'Loading...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
      <Loader2 className="h-7 w-7 animate-spin text-primary/50" />
      <span className="text-sm font-medium">{text}</span>
    </div>
  )
}
