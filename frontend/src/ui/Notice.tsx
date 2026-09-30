import clsx from 'clsx'
import { CircleAlert, Info, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

type Level = 'info' | 'warn' | 'danger'

const STYLE: Record<Level, { box: string; icon: string; Icon: typeof Info }> = {
  info: { box: 'bg-info-soft', icon: 'text-info-text', Icon: Info },
  warn: { box: 'bg-warn-soft', icon: 'text-warn-text', Icon: TriangleAlert },
  danger: { box: 'bg-danger-soft', icon: 'text-danger-text', Icon: CircleAlert },
}

export function Notice({ level = 'info', children, className }: { level?: Level; children: ReactNode; className?: string }) {
  const { box, icon, Icon } = STYLE[level]
  return (
    <div role={level === 'info' ? 'note' : 'alert'} className={clsx('flex gap-3 rounded-md p-3.5', box, className)}>
      <Icon className={clsx('mt-0.5 size-[18px] shrink-0', icon)} aria-hidden />
      <div className="min-w-0 text-[14px] leading-relaxed text-text">{children}</div>
    </div>
  )
}
