import { cn } from '@/lib/utils'

const colorMap: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 border-amber-200',
  processing: 'bg-blue-50 text-blue-700 border-blue-200',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
  active: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  archived: 'bg-gray-50 text-gray-600 border-gray-200',
  running: 'bg-blue-50 text-blue-700 border-blue-200',
}

export function StatusBadge({ status }: { status: string }) {
  const color = colorMap[status] || colorMap.pending
  return (
    <span className={cn(
      'inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium',
      color
    )}>
      {status}
    </span>
  )
}
