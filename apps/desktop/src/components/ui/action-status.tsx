// Upstream-Derived: apps/desktop/src/components/ui/action-status.tsx @ f033b7dbf (MIT)
import type { ReactNode } from 'react'

import { BrandLoader } from '@/components/ui/brand-loader'
import { Check } from '@/lib/icons'

// idle → saving → done label+icon for action buttons (create / rename / delete…).
export function ActionStatus({
  state,
  idle,
  busy,
  done,
  idleIcon = null
}: {
  state: 'done' | 'idle' | 'saving'
  idle: string
  busy: string
  done: string
  idleIcon?: ReactNode
}) {
  return (
    <>
      {state === 'saving' ? <BrandLoader decorative /> : state === 'done' ? <Check /> : idleIcon}
      {state === 'saving' ? busy : state === 'done' ? done : idle}
    </>
  )
}
