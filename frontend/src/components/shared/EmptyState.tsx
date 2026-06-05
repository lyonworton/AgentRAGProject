import { Inbox } from 'lucide-react'
import type { ReactNode } from 'react'

interface Props {
  title: string
  action?: ReactNode
}

export function EmptyState({ title, action }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-3 text-muted-foreground">
      <Inbox className="h-10 w-10" />
      <p className="text-sm">{title}</p>
      {action}
    </div>
  )
}
