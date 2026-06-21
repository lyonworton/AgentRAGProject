import { Card, CardContent } from '@/components/ui/card'
import { type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  icon: LucideIcon
  label: string
  value: number | string
  className?: string
}

export function StatsCard({ icon: Icon, label, value, className }: Props) {
  return (
    <Card className={cn("border-border/60 overflow-hidden", className)}>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/6 border border-primary/10 shrink-0">
          <Icon className="h-4.5 w-4.5 text-primary" strokeWidth={1.8} />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xl font-bold tracking-tight text-foreground/90">{value}</p>
          <p className="text-[11px] font-medium text-muted-foreground/60 uppercase tracking-wider mt-0.5">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}
