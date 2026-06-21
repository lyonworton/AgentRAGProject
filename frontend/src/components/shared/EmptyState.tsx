import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

interface Props {
  title: string
  action?: ReactNode
}

export function EmptyState({ title, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-muted-foreground/70">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/5 border border-primary/10">
        <Inbox className="h-6 w-6 text-primary/40" />
      </div>
      <p className="text-sm font-medium text-muted-foreground/80 text-center max-w-xs">{title}</p>
      {action}
    </div>
  )
}
