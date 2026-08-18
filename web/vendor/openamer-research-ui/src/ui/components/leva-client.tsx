'use client'

import { Leva } from 'leva'
import { useEffect, useState } from 'react'

export function LevaClient() {
  const [hidden, setHidden] = useState(true)

  useEffect(() => {
    setHidden(!new URLSearchParams(window.location.search).has('dev'))
  }, [])

  return <Leva {...{ hidden }} />
}
