import { describe, expect, it } from 'vitest'

import { xh } from './xh'

// Runtime text, not cache occupancy, is the localization contract.
describe('isiXhosa dynamic display text', () => {
  it.each([
    [0, '0 iiprofayile'],
    [1, '1 iprofayile'],
    [2, '2 iiprofayile'],
  ])('localizes profile count %i', (count, expected) => {
    expect(xh.profiles.count(count)).toBe(expected)
  })

  it.each([
    ['plugin count', xh.settings.plugins.count, '1 ifakiwe', '2 zifakiwe'],
    ['minutes ago', xh.settings.about.minAgo, '1 umzuzu odlulileyo', '2 imizuzu ezidlulileyo'],
    ['hours ago', xh.settings.about.hoursAgo, '1 iyure edlulileyo', '2 iiyure ezidlulileyo'],
    ['days ago', xh.settings.about.daysAgo, '1 usuku oludlulileyo', '2 iintsuku ezidlulileyo'],
    ['workers', xh.agents.workers, '1 umsebenzi', '2 abasebenzi'],
    ['working agents', xh.agents.workersActive, '1 osebenzayo', '2 abasebenzayo'],
    ['active agents', xh.agents.activeCount, '1 osebenzayo', '2 abasebenzayo'],
    ['failed agents', xh.agents.failedCount, '1 usilele', '2 basilele'],
    ['agent tools', xh.agents.toolsCount, '1 isixhobo', '2 izixhobo'],
    ['agent files', xh.agents.filesCount, '1 ifayile', '2 iifayile'],
    ['zones', xh.zones.zoneCount, '1 ummandla', '2 imimandla'],
    ['console messages', xh.preview.console.messages, '1 umyalezo wekhonsoli', '2 imiyalezo yekhonsoli'],
    ['selected messages', xh.preview.console.selected, '1 ikhethiwe', '2 zikhethiwe'],
    ['failed processes', xh.shell.statusbar.failed, '1 isilele', '2 zisilele'],
    ['running processes', xh.shell.statusbar.running, '1 iyasebenza', '2 ziyasebenza'],
    ['skill commands', xh.desktop.skillCommandsAvailable, '1 umyalelo wesakhono okhoyo.', '2 imiyalelo yezakhono ekhoyo.'],
    ['changed files', xh.statusStack.coding.changed, '1 itshintshiwe', '2 zitshintshiwe'],
    ['notifications', xh.notifications.more, '1 isaziso esongezelelweyo', '2 izaziso ezongezelelweyo'],
    ['new changes', xh.notifications.updateReadyMessage, '1 inguqu entsha ekhoyo.', '2 iinguqu ezintsha ezikhoyo.'],
    ['allowed services', xh.settings.appearance.embedsReset, 'Seta kwakhona 1 inkonzo evumelekileyo', 'Seta kwakhona 2 iinkonzo ezivumelekileyo'],
    ['pets', xh.settings.appearance.pet.count, '1 isilwanyana.', '2 izilwanyana.'],
    ['update changes', xh.settings.about.updateReady, 'Uhlaziyo olutsha lulungile (1 inguqu iqukiwe).', 'Uhlaziyo olutsha lulungile (2 iinguqu ziqukiwe).'],
    ['MCP tools', xh.settings.mcp.testOk, 'Kuqhagamshelwe — 1 isixhobo siyafumaneka', 'Kuqhagamshelwe — 2 izixhobo ziyafumaneka'],
    ['messages', xh.settings.sessions.messages, '1 umyalezo', '2 imiyalezo'],
    ['models', xh.settings.toolsets.modelCount, '1 imodeli', '2 iimodeli'],
    ['updated items', xh.skills.bulkUpdated, 'Kuhlaziyiwe 1 into kwiiseshoni ezintsha.', 'Kuhlaziyiwe 2 izinto kwiiseshoni ezintsha.'],
    ['findings', xh.skills.hub.findings, '1 into efunyenweyo', '2 izinto ezifunyenweyo'],
    ['map nodes', xh.starmap.importSuccess, 'Kulayishwe imephu ene-1 inodi.', 'Kulayishwe imephu ene-2 iinodi.'],
    ['agents', xh.agents.agentsCount, '1 i-arhente', '2 ii-arhente'],
    ['profile skills', xh.profiles.skills, '1 isakhono', '2 izakhono'],
    ['jobs', xh.cron.count, '1 umsebenzi', '2 imisebenzi'],
    ['attachments', xh.composer.attachments, '1 isincamatheliso', '2 izincamatheliso'],
    ['background subagents', xh.statusStack.subagents, '1 i-arhente encedisayo', '2 ii-arhente ezincedisayo'],
    ['additional changes', xh.updates.moreChanges, '+ 1 enye inguqu iqukiwe.', '+ 2 ezinye iinguqu ziqukiwe.'],
    ['installer lines', xh.install.lines, '1 umgca', '2 imigca'],
    ['status subagents', xh.shell.statusbar.subagents, '1 i-arhente encedisayo', '2 ii-arhente ezincedisayo'],
    ['console entries', xh.preview.console.sentMessage, '1 ingeniso yelog yongezwe kwindawo yokubhala', '2 iingeniso zelog zongezwe kwindawo yokubhala'],
  ])('localizes both branches for %s', (_label, render, singular, plural) => {
    expect(render(1)).toBe(singular)
    expect(render(2)).toBe(plural)
    expect(render(0)).not.toMatch(/\b(?:notification|notifications|service|services|profile|profiles|skill|skills|job|jobs|attachment|attachments|Subagents?|subagents?|changes?|included|lines?|log entry|messages?|models?|findings?|nodes?|agents?|items?)\b/)
  })

  it('preserves preformatted string counts rather than treating them as numbers', () => {
    expect(xh.commandCenter.actions('1')).toBe('Isenzo esi-1')
    expect(xh.commandCenter.actions('2')).toBe('Izenzo ezi-2')
    expect(xh.commandCenter.actions('1,234')).toBe('Izenzo ezi-1,234')
  })

  it('localizes nullable timing text including a zero duration', () => {
    expect(xh.skills.hub.resultCount(1, null)).toBe('1 isiphumo')
    expect(xh.skills.hub.resultCount(2, 0)).toBe('2 iziphumo nge-0ms')
    expect(xh.skills.hub.resultCount(2, 17)).toBe('2 iziphumo nge-17ms')
  })

  it('keeps the branch name while translating commit-count text', () => {
    expect(xh.shell.statusbar.commitsBehind(1, 'main')).toBe('1 ugcino lwe-git emva kwe-main')
    expect(xh.shell.statusbar.commitsBehind(2, 'main')).toBe('2 izigcino ze-git emva kwe-main')
  })

  it('localizes the unknown file-type branch without changing actual MIME types', () => {
    expect(xh.preview.noInlineBody('')).toBe('Olu hlobo lwefayile lusenokuncanyathiselwa njengomxholo.')
    expect(xh.preview.noInlineBody('application/pdf')).toBe('application/pdf lusenokuncanyathiselwa njengomxholo.')
  })

  it('localizes both YOLO display states without changing the state', () => {
    expect(xh.desktop.yoloSystem(true)).toBe('I-YOLO ivuliwe kule seshoni')
    expect(xh.desktop.yoloSystem(false)).toBe('I-YOLO icinyiwe kule seshoni')
  })

  it('localizes non-template expressions excluded by the string extractor', () => {
    expect(xh.assistant.thread.resumeWhenBackgroundDone(1)).toBe('Iza kuqhubeka xa umsebenzi wangasemva ugqityiwe')
    expect(xh.assistant.thread.resumeWhenBackgroundDone(2)).toBe('Iza kuqhubeka xa imisebenzi yangasemva eyi-2 igqityiwe')
    expect(xh.sidebar.projects.branchOff()).toEqual({ after: '', before: 'yenza isebe elisuka ku-' })
    expect(xh.settings.appearance.product).toBe('Imveliso')
    expect(xh.settings.appearance.technical).toBe('Ezobugcisa')
  })

  it('uses translated settings labels in explanatory text', () => {
    for (const label of [xh.settings.appearance.embedsAsk, xh.settings.appearance.embedsAlways, xh.settings.appearance.embedsOff]) {
      expect(xh.settings.appearance.embedsDesc).toContain(label)
    }

    expect(xh.settings.about.branchCommit('main', 'abc123')).toBe('Isebe main · Ugcino lwe-git abc123')
  })

  it('localizes nested MCP capability templates with optional entries', () => {
    expect(xh.settings.mcp.capabilitySummary(1, 0, 0)).toBe('Kuvuliwe: 1 isixhobo')
    expect(xh.settings.mcp.capabilitySummary(2, 1, 1)).toBe('Kuvuliwe: 2 izixhobo, 1 umyalelo, 1 isixhobo sedatha')
    expect(xh.settings.mcp.capabilitySummary(2, 2, 2)).toBe('Kuvuliwe: 2 izixhobo, 2 imiyalelo, 2 izixhobo zedatha')
  })
})
