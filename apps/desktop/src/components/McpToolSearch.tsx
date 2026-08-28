import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Codicon } from "@/components/ui/codicon"
import type { McpCommunityResponse, McpSearchToolsResponse } from "@/types/openamer"
import { searchCommunityMcpCatalog, searchMcpTools } from "@/openamer"

/**
 * Tool / server discovery for the MCP tab (Desktop renderer).
 *
 * Mirrors the dashboard's Discovery panel: two searches over the same
 * auth-gated backend endpoints —
 *   1. installed tools:  /api/mcp/search-tools  (Layer-1, grouped by server)
 *   2. community catalog: /api/a2a/mcp-catalog  (punkpeye ~1.9k servers)
 * Query syntax: space = AND, a|b = OR, "exact phrase".
 */
export function McpToolSearch() {
  const [toolQ, setToolQ] = useState("")
  const [toolResult, setToolResult] = useState<McpSearchToolsResponse | null>(null)
  const [toolLoading, setToolLoading] = useState(false)
  const [toolRan, setToolRan] = useState(false)

  const [communityQ, setCommunityQ] = useState("")
  const [community, setCommunity] = useState<McpCommunityResponse | null>(null)
  const [communityLoading, setCommunityLoading] = useState(false)
  const [communityRan, setCommunityRan] = useState(false)

  async function runTools() {
    if (!toolQ.trim()) return
    setToolLoading(true)
    setToolRan(true)
    try {
      setToolResult(await searchMcpTools(toolQ.trim()))
    } catch {
      setToolResult(null)
    } finally {
      setToolLoading(false)
    }
  }

  async function runCommunity() {
    if (!communityQ.trim()) return
    setCommunityLoading(true)
    setCommunityRan(true)
    try {
      setCommunity(await searchCommunityMcpCatalog(communityQ.trim()))
    } catch {
      setCommunity(null)
    } finally {
      setCommunityLoading(false)
    }
  }

  return (
    <div className="flex flex-col gap-3 border-t pt-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Codicon name="search" />
        Discovery
        <span className="text-xs font-normal opacity-60">
          space=AND · a|b=OR · “phrase”
        </span>
      </div>

      {/* Installed-tool search */}
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-1.5">
          <Input
            value={toolQ}
            placeholder="Find a tool across installed servers"
            onChange={e => setToolQ(e.target.value)}
            onKeyDown={e => e.key === "Enter" && runTools()}
          />
          <Button size="sm" onClick={runTools} disabled={toolLoading || !toolQ.trim()}>
            {toolLoading ? "…" : "Search"}
          </Button>
        </div>
        {toolRan && toolResult && (
          <div className="text-xs opacity-70">
            {toolResult.count} tool(s) across {toolResult.total_servers} server(s)
          </div>
        )}
        {toolRan && toolResult && toolResult.matches.length > 0 && (
          <div className="flex flex-col gap-1">
            {toolResult.matches.map(m => (
              <div key={`${m.server}::${m.name}`} className="flex items-start gap-2 text-xs">
                <code className="shrink-0 text-primary">{m.server}::{m.name}</code>
                <span className="opacity-70">{m.description}</span>
              </div>
            ))}
          </div>
        )}
        {toolRan && toolResult && toolResult.matches.length === 0 && (
          <div className="text-xs opacity-60">No matching tools.</div>
        )}
        {toolResult && toolResult.probe_errors.length > 0 && (
          <div className="text-xs text-warning">
            {toolResult.probe_errors.length} server(s) could not be probed.
          </div>
        )}
      </div>

      {/* Community catalog search */}
      <div className="flex flex-col gap-1.5">
        <div className="flex gap-1.5">
          <Input
            value={communityQ}
            placeholder="Search community MCP catalog (e.g. github, postgres)"
            onChange={e => setCommunityQ(e.target.value)}
            onKeyDown={e => e.key === "Enter" && runCommunity()}
          />
          <Button size="sm" onClick={runCommunity} disabled={communityLoading || !communityQ.trim()}>
            {communityLoading ? "…" : "Search"}
          </Button>
        </div>
        {communityRan && community && (
          <div className="text-xs opacity-70">{community.count} server(s) found</div>
        )}
        {communityRan && community && community.entries.length === 0 && (
          <div className="text-xs opacity-60">No matching servers.</div>
        )}
        {community && community.entries.length > 0 && (
          <div className="flex flex-col gap-1">
            {community.entries.map(e => (
              <div key={e.url} className="flex items-start gap-2 text-xs">
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="shrink-0 text-primary underline underline-offset-2 hover:opacity-80"
                >
                  {e.name}
                </a>
                <span className="opacity-70 flex-1">{e.description}</span>
                {e.curated ? (
                  <span className="shrink-0 text-emerald-500">approved</span>
                ) : e.installed ? (
                  <span className="shrink-0 opacity-60">installed</span>
                ) : null}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}