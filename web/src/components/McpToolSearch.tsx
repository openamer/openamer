import { useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@openamer-research/ui/ui/components/badge";
import { Button } from "@openamer-research/ui/ui/components/button";
import { Card, CardContent } from "@openamer-research/ui/ui/components/card";
import { Input } from "@openamer-research/ui/ui/components/input";
import { Label } from "@openamer-research/ui/ui/components/label";
import { Spinner } from "@openamer-research/ui/ui/components/spinner";
import { H2 } from "@openamer-research/ui/ui/components/typography/h2";
import { api } from "@/lib/api";
import type {
  McpSearchToolsResponse,
  McpCommunityEntry,
} from "@/lib/api";

/**
 * Tool / server discovery search for the MCP page.
 *
 * Two complementary searches:
 *  1. Community catalog (``openamer a2a mcp-catalog``): find an MCP *server*
 *     in the broad third-party registry (~1989 entries). Entries already in
 *     the OpenAmer-approved catalog are marked [approved] so install is safe.
 *  2. Installed tools (`openamer mcp search-tools`): find a *tool* across the
 *     servers you've already installed, grouped by source server — the 2026
 *     MCP progressive-discovery / Layer-1 pattern. Query syntax: space=AND,
 *     `a|b`=OR, `"exact phrase"`.
 */
export default function McpToolSearch() {
  const [communityQ, setCommunityQ] = useState("");
  const [community, setCommunity] = useState<McpCommunityEntry[]>([]);
  const [communityCount, setCommunityCount] = useState(0);
  const [communityLoading, setCommunityLoading] = useState(false);
  const [communityRan, setCommunityRan] = useState(false);

  const [toolQ, setToolQ] = useState("");
  const [tools, setTools] = useState<McpSearchToolsResponse | null>(null);
  const [toolLoading, setToolLoading] = useState(false);
  const [toolRan, setToolRan] = useState(false);

  async function runCommunity() {
    if (!communityQ.trim()) return;
    setCommunityLoading(true);
    setCommunityRan(true);
    try {
      const res = await api.searchCommunityMcpCatalog(communityQ.trim());
      setCommunity(res.entries);
      setCommunityCount(res.count);
    } catch {
      setCommunity([]);
      setCommunityCount(0);
    } finally {
      setCommunityLoading(false);
    }
  }

  async function runTools() {
    if (!toolQ.trim()) return;
    setToolLoading(true);
    setToolRan(true);
    try {
      setTools(await api.searchMcpTools(toolQ.trim()));
    } catch {
      setTools(null);
    } finally {
      setToolLoading(false);
    }
  }

  return (
    <div className="mt-6 flex flex-col gap-4">
      <H2 variant="sm" className="flex items-center gap-2 text-muted-foreground">
        <Search className="h-4 w-4" />
        Discovery
      </H2>
      <p className="text-xs text-muted-foreground">
        Find a tool you may already have installed, or a ready-made MCP server
        in the community catalog. Query syntax: <code>space = AND</code>,{" "}
        <code>a|b = OR</code>, <code>&quot;exact phrase&quot;</code>.
      </p>

      {/* Tool search across installed servers */}
      <Card>
        <CardContent className="flex flex-col gap-3 py-4">
          <Label>Search installed tools</Label>
          <div className="flex gap-2">
            <Input
              placeholder="e.g. update salesforce record"
              value={toolQ}
              onChange={(e) => setToolQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runTools()}
            />
            <Button
              onClick={runTools}
              disabled={toolLoading || !toolQ.trim()}
              prefix={toolLoading ? <Spinner /> : undefined}
            >
              Search
            </Button>
          </div>
          {toolRan && !toolLoading && tools && (
            <div className="text-xs text-muted-foreground">
              {tools.count} tool match(es) across {tools.total_servers} server(s)
            </div>
          )}
          {toolRan && !toolLoading && tools && tools.matches.length === 0 && (
            <p className="text-xs text-muted-foreground">No matching tools.</p>
          )}
          {toolRan && !toolLoading && tools && tools.matches.length > 0 && (
            <div className="flex flex-col gap-1.5">
              {tools.matches.map((m) => (
                <div
                  key={`${m.server}::${m.name}`}
                  className="flex items-start gap-2 text-sm"
                >
                  <code className="font-mono text-xs text-primary shrink-0 whitespace-nowrap">
                    {m.server}::{m.name}
                  </code>
                  <span className="text-muted-foreground text-xs">
                    {m.description}
                  </span>
                </div>
              ))}
            </div>
          )}
          {tools && tools.probe_errors.length > 0 && (
            <p className="text-xs text-warning">
              {tools.probe_errors.length} server(s) could not be probed.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Community catalog search */}
      <Card>
        <CardContent className="flex flex-col gap-3 py-4">
          <Label>Search community MCP catalog</Label>
          <div className="flex gap-2">
            <Input
              placeholder="e.g. github or postgres"
              value={communityQ}
              onChange={(e) => setCommunityQ(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runCommunity()}
            />
            <Button
              onClick={runCommunity}
              disabled={communityLoading || !communityQ.trim()}
              prefix={communityLoading ? <Spinner /> : undefined}
            >
              Search
            </Button>
          </div>
          {communityRan && !communityLoading && (
            <div className="text-xs text-muted-foreground">
              {communityCount} server(s) found
            </div>
          )}
          {communityRan && !communityLoading && community.length === 0 && (
            <p className="text-xs text-muted-foreground">No matching servers.</p>
          )}
          <div className="flex flex-col gap-1.5">
            {community.map((e) => (
              <div
                key={e.url}
                className="flex items-start gap-2 text-sm"
              >
                <a
                  href={e.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-mono text-xs text-primary underline underline-offset-2 hover:opacity-80 shrink-0"
                >
                  {e.name}
                </a>
                <span className="text-muted-foreground text-xs flex-1">
                  {e.description}
                </span>
                {e.curated ? (
                  <Badge tone="success">approved</Badge>
                ) : (
                  e.installed && <Badge tone="outline">installed</Badge>
                )}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}