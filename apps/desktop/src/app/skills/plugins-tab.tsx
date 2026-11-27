import { useMutation, useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'

import { PageLoader } from '@/components/page-loader'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { Input } from '@/components/ui/input'
import { useI18n } from '@/i18n'
import { compactNumber } from '@/lib/format'
import { queryClient } from '@/lib/query-client'
import { getPluginsHub, installAgentPlugin, rescanPlugins, searchAgentPlugins, setAgentPluginEnabled } from '@/openamer'
import { notify, notifyError } from '@/store/notifications'
import type { AgentPluginRow, PluginsHub } from '@/types/openamer'

import { CapRow, ListColumn } from '../master-detail'
import { PanelEmpty, PanelPill } from '../overlays/panel'

import { isPluginOn as isOn, pluginMatches, pluginStatusKey } from './plugins'

const PLUGINS_QUERY_KEY = ['plugins-hub'] as const

// Stable identity so `?? []` never re-arms the filter memo on every render.
const NO_PLUGINS: AgentPluginRow[] = []

function PluginRow({ row, busy, onToggle }: { row: AgentPluginRow; busy: boolean; onToggle: (next: boolean) => void }) {
  const { t } = useI18n()

  return (
    <CapRow
      active={false}
      busy={busy}
      enabled={isOn(row)}
      meta={row.version ? <PanelPill>{row.version}</PanelPill> : null}
      onSelect={() => onToggle(!isOn(row))}
      onToggle={onToggle}
      rowId={row.name}
      subtitle={
        <span className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate">{row.description || row.path}</span>
          <span className="flex items-center gap-1.5 text-xs opacity-70">
            <PanelPill>{row.source || 'local'}</PanelPill>
            <span>{t.skills[pluginStatusKey(row)]}</span>
            {row.auth_required && row.auth_command ? <code className="truncate">{row.auth_command}</code> : null}
          </span>
        </span>
      }
      title={row.name}
      toggleLabel={isOn(row) ? t.settings.plugins.disable : t.settings.plugins.enable}
    />
  )
}

export function PluginsTab({ query }: { query: string }) {
  const { t } = useI18n()
  const [identifier, setIdentifier] = useState('')
  const [pending, setPending] = useState<string | null>(null)

  const hub = useQuery<PluginsHub>({
    queryFn: getPluginsHub,
    queryKey: PLUGINS_QUERY_KEY
  })

  const rows = hub.data?.plugins ?? NO_PLUGINS
  const needle = query.trim().toLowerCase()
  const filtered = useMemo(() => rows.filter(row => pluginMatches(row, needle)), [needle, rows])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: PLUGINS_QUERY_KEY })

  const toggle = useMutation({
    mutationFn: ({ enabled, name }: { enabled: boolean; name: string }) => setAgentPluginEnabled(name, enabled),
    onError: err => notifyError(err, t.skills.pluginsToggleFailed),
    onMutate: ({ name }) => setPending(name),
    onSettled: async () => {
      setPending(null)
      await invalidate()
    }
  })

  const install = useMutation({
    mutationFn: (id: string) => installAgentPlugin(id, { enable: true }),
    onError: err => notifyError(err, t.skills.pluginsInstallFailed),
    onSuccess: async (_result, id) => {
      setIdentifier('')
      notify({ kind: 'success', message: t.skills.pluginsInstallOk(id) })
      await invalidate()
    }
  })

  const rescan = useMutation({
    mutationFn: rescanPlugins,
    onError: err => notifyError(err, t.skills.pluginsRescanFailed),
    onSuccess: async () => {
      await invalidate()
    }
  })

  // Discovery only runs when asked: the backend hits GitHub's search API, which
  // is rate limited, and an empty answer is ambiguous ("no match" vs "limited").
  const discover = useMutation({
    mutationFn: (query: string) => searchAgentPlugins(query),
    onError: err => notifyError(err, t.skills.pluginsSearchFailed)
  })

  if (hub.isPending) {
    return <PageLoader label={t.skills.loading} />
  }

  if (hub.isError) {
    return (
      <PanelEmpty
        action={
          <Button onClick={() => void hub.refetch()} size="sm">
            {t.skills.refresh}
          </Button>
        }
        description={hub.error instanceof Error ? hub.error.message : undefined}
        icon="error"
        title={t.skills.pluginsLoadFailed}
      />
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-2 px-3 py-2">
        <Input
          className="min-w-52 flex-1"
          onChange={event => setIdentifier(event.target.value)}
          placeholder={t.skills.pluginsInstallPlaceholder}
          value={identifier}
        />
        <Button
          disabled={!identifier.trim() || install.isPending}
          onClick={() => install.mutate(identifier.trim())}
          size="sm"
        >
          <Codicon name={install.isPending ? 'loading~spin' : 'cloud-download'} size="0.85rem" />
          {t.skills.pluginsInstall}
        </Button>
        <Button disabled={rescan.isPending} onClick={() => rescan.mutate()} size="sm" variant="ghost">
          <Codicon name={rescan.isPending ? 'loading~spin' : 'refresh'} size="0.85rem" />
          {t.skills.pluginsRescan}
        </Button>
      </div>

      {needle ? (
        <div className="shrink-0 border-b border-(--ui-stroke-tertiary) px-3 py-2">
          {discover.data ? (
            discover.data.results.length > 0 ? (
              <div className="flex flex-col gap-1.5">
                <span className="text-xs opacity-70">
                  {t.skills.pluginsDiscoverResults(discover.data.results.length, discover.data.query)}
                </span>
                {discover.data.results.map(hit => (
                  <div className="flex items-center justify-between gap-2" key={hit.full_name}>
                    <span className="flex min-w-0 flex-col">
                      <span className="flex items-center gap-1.5 truncate text-sm">
                        {hit.full_name}
                        <PanelPill>{`★ ${compactNumber(hit.stargazers_count)}`}</PanelPill>
                      </span>
                      <span className="truncate text-xs opacity-70">{hit.description ?? ''}</span>
                    </span>
                    <Button
                      disabled={install.isPending}
                      onClick={() => install.mutate(hit.full_name)}
                      size="sm"
                      variant="outline"
                    >
                      <Codicon name="cloud-download" size="0.85rem" />
                      {t.skills.pluginsInstall}
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <span className="text-xs opacity-70">{t.skills.pluginsDiscoverEmpty(discover.data.query)}</span>
            )
          ) : (
            <Button disabled={discover.isPending} onClick={() => discover.mutate(needle)} size="sm" variant="outline">
              <Codicon name={discover.isPending ? 'loading~spin' : 'search'} size="0.85rem" />
              {t.skills.pluginsDiscoverAction(needle)}
            </Button>
          )}
        </div>
      ) : null}

      {filtered.length === 0 ? (
        <PanelEmpty
          description={t.skills.pluginsEmptyDesc}
          icon="extensions"
          title={needle ? t.skills.pluginsNoMatch : t.skills.pluginsEmptyTitle}
        />
      ) : (
        <ListColumn header={<span className="px-2 pb-1 text-xs opacity-70">{t.skills.pluginsCount(rows.length)}</span>}>
          {filtered.map(row => (
            <PluginRow
              busy={pending === row.name}
              key={row.name}
              onToggle={next => toggle.mutate({ enabled: next, name: row.name })}
              row={row}
            />
          ))}
        </ListColumn>
      )}
    </div>
  )
}
