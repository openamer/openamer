import { useQuery } from '@tanstack/react-query'

import { getOpenAmerConfigRecord } from '@/openamer'
import { queryClient, writeCache } from '@/lib/query-client'
import type { OpenAmerConfigRecord } from '@/types/openamer'

// One shared cache for the whole profile config record (`GET /api/config`).
// Every settings surface (MCP, model, config) reads and writes through this key
// so a save in one shows in the others, and revisiting a tab paints the cache
// instead of blanking on a fresh fetch.
//
// Distinct from session/hooks/use-openamer-config.ts, which is side-effecting —
// it pushes personality/cwd/voice/… into the session stores for live chat.
export const OPENAMER_CONFIG_KEY = ['openamer-config-record'] as const

// staleTime 0 → serve cache instantly, background-revalidate on every mount.
export const useOpenAmerConfigRecord = () =>
  useQuery({ queryKey: OPENAMER_CONFIG_KEY, queryFn: getOpenAmerConfigRecord, staleTime: 0 })

export const setOpenAmerConfigCache = writeCache<OpenAmerConfigRecord>(OPENAMER_CONFIG_KEY)

export const invalidateOpenAmerConfig = () => queryClient.invalidateQueries({ queryKey: OPENAMER_CONFIG_KEY })
