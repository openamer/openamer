/**
 * Darwin Evolution — live skill-evolution dashboard page (Docusaurus).
 * Shows real Darwin Engine data: fitness leaderboard, lineage stats,
 * latest autopatch report, trend→skill synthesis feed.
 * Data source: /darwin/darwin-status.json (refreshed daily by cron,
 * committed to website/static/darwin/).
 */
import React from "react";
import useDocusaurusContext from "@docusaurus/useDocusaurusContext";
import Layout from "@theme/Layout";
import styles from "./darwin.module.css";

type SkillRow = { name: string; score: number };
type DarwinStatus = {
  updated: string;
  population: number;
  species: number;
  trials: number;
  harvested: number;
  avg_score: number;
  fittest: SkillRow[];
  autopatch: { timestamp: string; kept: { skill: string; before: number; after: number }[] };
  trends: { title: string; url: string; source: string }[];
};

function loadStatus(): DarwinStatus | null {
  return null; // placeholder — fetched client-side below
}

export default function Darwin(): React.ReactElement {
  const { siteConfig } = useDocusaurusContext();
  const [status, setStatus] = React.useState<DarwinStatus | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  React.useEffect(() => {
    fetch(`${siteConfig.baseUrl}darwin/darwin-status.json`)
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setStatus)
      .catch((e) => setErr(String(e)));
  }, [siteConfig.baseUrl]);

  return (
    <Layout title="Darwin Evolution" description="Live skill evolution of the OpenAmer agent">
      <main className="container margin-vert--lg">
        <h1>🧬 Darwin Evolution</h1>
        <p>
          The OpenAmer agent improves itself: skills carry fitness scores, get
          automatically patched (Darwin AutoPatch), compete in live trials, and new
          species are synthesized from daily trend intelligence. This page shows the
          real numbers — updated daily, zero manual curation.
        </p>

        {err && (
          <div className="alert alert--warning">
            Status data not available yet ({err}). The daily cron will publish it — check back soon.
          </div>
        )}

        {status && (
          <>
            <section className="row margin-vert--md">
              <div className="col col--3"><div className="card padding--md"><h3>{status.population}</h3><p>skills tracked</p></div></div>
              <div className="col col--3"><div className="card padding--md"><h3>{status.species}</h3><p>species installed</p></div></div>
              <div className="col col--3"><div className="card padding--md"><h3>{status.avg_score}</h3><p>avg fitness</p></div></div>
              <div className="col col--3"><div className="card padding--md"><h3>{status.trials}</h3><p>live trials</p></div></div>
            </section>

            <h2>Fittest skills</h2>
            <table>
              <thead><tr><th>Skill</th><th>Fitness</th></tr></thead>
              <tbody>
                {status.fittest.map((s) => (
                  <tr key={s.name}><td><code>{s.name}</code></td><td>{s.score}</td></tr>
                ))}
              </tbody>
            </table>

            {status.autopatch?.kept?.length > 0 && (
              <>
                <h2>Latest AutoPatch (auto-repairs, verified)</h2>
                <ul>
                  {status.autopatch.kept.map((k) => (
                    <li key={k.skill}>
                      <code>{k.skill}</code>: {k.before} → <strong>{k.after}</strong>
                    </li>
                  ))}
                </ul>
              </>
            )}

            {status.trends?.length > 0 && (
              <>
                <h2>Trend radar → future skills</h2>
                <p>What the agent is reading today becomes tomorrow's skill candidates.</p>
                <ul>
                  {status.trends.map((t) => (
                    <li key={t.url}>
                      <span className="badge badge--secondary">{t.source}</span>{" "}
                      <a href={t.url} target="_blank" rel="noopener noreferrer">{t.title}</a>
                    </li>
                  ))}
                </ul>
              </>
            )}

            <p className="text--muted">Last update: {status.updated}</p>
          </>
        )}
      </main>
    </Layout>
  );
}
