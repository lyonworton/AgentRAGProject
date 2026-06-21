import { cn } from '@/lib/utils'

const colorMap: Record<string, string> = {
  pending: 'bg-amber-50 text-amber-700 border-amber-200/60',
  processing: 'bg-sky-50 text-sky-700 border-sky-200/60',
  completed: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
  failed: 'bg-red-50 text-red-700 border-red-200/60',
  active: 'bg-emerald-50 text-emerald-700 border-emerald-200/60',
  archived: 'bg-gray-50 text-gray-600 border-gray-200/60',
  running: 'bg-sky-50 text-sky-700 border-sky-200/60',
  canceled: 'bg-gray-50 text-gray-600 border-gray-200/60',
  error: 'bg-red-50 text-red-700 border-red-200/60',
}

export function StatusBadge({ status }: { status: string }) {
  const color = colorMap[status.toLowerCase()] || colorMap.pending
  return (
    <span className={cn(
      'inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide uppercase',
      color
    )}>
      {status}
    </span>
  )
}
