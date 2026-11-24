# Reddit comment verification walk — 2026-10-12 session

## Symptom
After posting a comment via `POST /api/comment` (cid `t1_pfc169s` on thread `1x3ekrr`, r/AI_Agents),
the verification walk over `/r/AI_Agents/comments/1x3ekrr.json?limit=500` returned the literal string
`{}` — six consecutive times — even though the same expression worked on the first try once the tab
was navigated to the thread's own URL.

## The two expressions (identical)
```js
(async()=>{
  const j = await (await fetch('/r/AI_Agents/comments/1x3ekrr.json?limit=500',{credentials:'same-origin'})).json();
  const post = j[0].data.children[0].data;
  const walk = (c,acc) => { if (c.data.author==='Realistic_Kitchen_65') acc.push(c.data.id);
                            (c.replies && c.replies.data && c.replies.data.children || []).forEach(x=>walk(x,acc)); };
  const acc = []; (j[1] && j[1].data && j[1].data.children || []).forEach(c=>walk(c,acc));
  return JSON.stringify({title:post.title, selftext:(post.selftext||'').slice(0,300), mine:acc,
                         ncomments:(j[1]&&j[1].data&&j[1].data.children||[]).length});
})()
```
- Tab navigated to `https://old.reddit.com/` → returns `"{}"` (6/6 attempts)
- Tab navigated to `https://old.reddit.com/r/AI_Agents/comments/1x3ekrr/` → returns the full object (1/1)

## Recovery (evidence-backed, root cause NOT isolated)
Before concluding a comment is absent or a thread unreadable:
1. `Page.navigate` the tab to `https://old.reddit.com/r/<sub>/comments/<pid>/` (the thread's own URL).
2. Re-run the same walk expression.
3. Only if it STILL returns `{}` treat the read as inconclusive and say so.

Do not write this down as a proven mechanism — the fetch is same-origin from both pages, so the
likely contributor is tab state (a parallel cron hijacking the tab to Bing is the documented pattern
here), but the mechanism was not isolated in this session. The recovery step is what is durable.

## What did work (the authoritative comment proof, unchanged)
`GET /api/info.json?id=t1_<cid>&raw_json=1` in-page → `{id, author, subreddit, link_id, score,
removed_by_category, body}`. This run: `t1_pfc169s`, author `Realistic_Kitchen_65`, sub `AI_Agents`,
link `t3_1x3ekrr`, score 1, `removed_by_category: null`, bodylen 1317.

## Thread that matched
`1x3ekrr` — "our agent job failed. the UI still showed a success toast." (259 min old at post time,
r/AI_Agents, 10 comments). Theme fit: receipt-before-effect ordering, "effect landed, receipt missing"
vs. "receipt landed, effect missing", `why`-field value over boolean. Discovered via
`/r/AI_Agents/new.json?limit=40` filtered to `age_min < 720` — the 259-min window is comfortably
inside the skill's `age_min < ~400` guidance.