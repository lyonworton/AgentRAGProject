import { Loader2 } from 'lucide-react'

export function StatusBar({ message }: { message: string | null }) {
  if (!message) return null
  return (
    <div className="flex items-center gap-2 px-4 py-1.5 text-xs text-muted-foreground bg-muted/50 rounded-md">
      <Loader2 className="h-3 w-3 animate-spin" />
      {message}
    </div>
  )
}
