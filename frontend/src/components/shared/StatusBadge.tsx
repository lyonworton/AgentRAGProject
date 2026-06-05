import { cn } from '@/lib/utils'

const colorMap: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-700',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  active: 'bg-green-100 text-green-700',
  archived: 'bg-gray-100 text-gray-700',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span className={cn('inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium', colorMap[status] || colorMap.pending)}>
      {status}
    </span>
  )
}
