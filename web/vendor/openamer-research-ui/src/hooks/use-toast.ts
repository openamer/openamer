'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

export function useToast(duration = 3000) {
  const [toast, setToast] = useState<{
    message: string
    type: 'error' | 'success'
  } | null>(null)

  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current)
    }
  }, [])

  const showToast = useCallback(
    (message: string, type: 'error' | 'success') => {
      if (timerRef.current) clearTimeout(timerRef.current)
      setToast({ message, type })
      timerRef.current = setTimeout(() => setToast(null), duration)
    },
    [duration]
  )

  return { showToast, toast }
}
