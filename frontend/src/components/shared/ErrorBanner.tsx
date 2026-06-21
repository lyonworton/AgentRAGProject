import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface Props {
  message: string
  onRetry?: () => void
}

export function ErrorBanner({ message, onRetry }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-destructive/8">
        <AlertTriangle className="h-5 w-5 text-destructive/70" />
      </div>
      <p className="text-sm text-destructive/80 text-center max-w-md font-medium">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry} className="rounded-lg">
          Try again
        </Button>
      )}
    </div>
  )
}
