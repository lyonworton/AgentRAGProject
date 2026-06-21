import { Card, CardContent } from '@/components/ui/card'
import { type LucideIcon } from 'lucide-react'

interface Props {
  icon: LucideIcon
  label: string
  value: number | string
}

export function StatsCard({ icon: Icon, label, value }: Props) {
  return (
    <Card className="border-border/80">
      <CardContent className="flex items-center gap-4 p-6">
        <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/8">
          <Icon className="h-5 w-5 text-primary" />
        </div>
        <div>
          <p className="text-2xl font-bold tracking-tight">{value}</p>
          <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}
