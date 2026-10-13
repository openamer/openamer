'use client'

import { useRef } from 'react'
import { AlertDialog as AlertDialogPrimitive } from 'radix-ui'

import { cn } from '../../utils'
import { Button } from './button'

function WarningTriangle({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden
      className={className}
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="m10.29 3.86-8.16 14a2 2 0 0 0 1.73 3h16.28a2 2 0 0 0 1.73-3l-8.16-14a2 2 0 0 0-3.46 0z" />
      <line x1="12" x2="12" y1="9" y2="13" />
      <line x1="12" x2="12.01" y1="17" y2="17" />
    </svg>
  )
}

export function ConfirmDialog({
  cancelLabel = 'Cancel',
  confirmLabel = 'Confirm',
  description,
  destructive = false,
  loading = false,
  onCancel,
  onConfirm,
  open,
  title
}: ConfirmDialogProps) {
  const confirmedRef = useRef(false)

  return (
    <AlertDialogPrimitive.Root
      onOpenChange={v => {
        if (!v && !confirmedRef.current) onCancel()
        confirmedRef.current = false
      }}
      open={open}
    >
      <AlertDialogPrimitive.Portal>
        <AlertDialogPrimitive.Overlay
          className={cn(
            'fixed inset-0 z-50',
            'bg-black/60 backdrop-blur-sm',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0'
          )}
        />

        <AlertDialogPrimitive.Content
          className={cn(
            'fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2',
            'w-[calc(100%-2rem)] max-w-md',
            'border border-midground/15 bg-background-base text-foreground-base shadow-lg outline-none',
            'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95',
            'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95',
            'duration-150'
          )}
        >
          <div className="flex items-start gap-3 p-4 border-b border-midground/15">
            {destructive && (
              <div aria-hidden className="mt-0.5 shrink-0 text-destructive">
                <WarningTriangle className="h-4 w-4" />
              </div>
            )}

            <div className="flex-1 min-w-0 flex flex-col gap-1">
              <AlertDialogPrimitive.Title
                className="font-expanded text-sm font-bold tracking-[0.08em] uppercase"
              >
                {title}
              </AlertDialogPrimitive.Title>

              {description && (
                <AlertDialogPrimitive.Description
                  className="font-mondwest text-xs text-midground/60 leading-relaxed"
                >
                  {description}
                </AlertDialogPrimitive.Description>
              )}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 p-3">
            <AlertDialogPrimitive.Cancel asChild>
              <Button disabled={loading} outlined type="button">
                {cancelLabel}
              </Button>
            </AlertDialogPrimitive.Cancel>

            <AlertDialogPrimitive.Action asChild>
              <Button
                destructive={destructive}
                disabled={loading}
                onClick={() => {
                  confirmedRef.current = true
                  onConfirm()
                }}
                type="button"
              >
                {loading ? '…' : confirmLabel}
              </Button>
            </AlertDialogPrimitive.Action>
          </div>
        </AlertDialogPrimitive.Content>
      </AlertDialogPrimitive.Portal>
    </AlertDialogPrimitive.Root>
  )
}

interface ConfirmDialogProps {
  cancelLabel?: string
  confirmLabel?: string
  description?: string
  destructive?: boolean
  loading?: boolean
  onCancel: () => void
  onConfirm: () => void
  open: boolean
  title: string
}
