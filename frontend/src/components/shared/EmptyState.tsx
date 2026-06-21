import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

interface Props {
  title: string
  action?: ReactNode
}

export function EmptyState({ title, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
      <div className="flex h-12 w-12 items-center justify-center rounded-full bg-muted/80">
        <Inbox className="h-5 w-5 text-muted-foreground/70" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      {action}
    </div>
  )
}
