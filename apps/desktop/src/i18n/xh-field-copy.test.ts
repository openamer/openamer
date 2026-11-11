import { describe, expect, it } from 'vitest'

import { FIELD_DESCRIPTIONS, FIELD_LABELS } from '@/app/settings/constants'

import { xh } from './xh'

// Imported records are deliberately outside the main locale's static extractor.
describe('isiXhosa settings field copy', () => {
  it('covers the complete English field-label and description key sets', () => {
    expect(Object.keys(xh.settings.fieldLabels).sort()).toEqual(Object.keys(FIELD_LABELS).sort())
    expect(Object.keys(xh.settings.fieldDescriptions).sort()).toEqual(Object.keys(FIELD_DESCRIPTIONS).sort())
  })

  it('does not inherit English field labels', () => {
    expect(Object.entries(FIELD_LABELS)
      .filter(([key, value]) => xh.settings.fieldLabels[key] === value)
      .map(([key]) => key)).toEqual([])
    expect(xh.settings.fieldLabels.model).toBe('Imodeli yokungagqibekanga')
  })

  it('does not inherit English field descriptions', () => {
    expect(Object.entries(FIELD_DESCRIPTIONS)
      .filter(([key, value]) => xh.settings.fieldDescriptions[key] === value)
      .map(([key]) => key)).toEqual([])
  })

  it('preserves executable option values and audio-tag syntax', () => {
    expect(xh.settings.fieldDescriptions['tts.xai.autoSpeechTags']).toContain('[laughing], [sighs]')
    expect(xh.settings.fieldDescriptions['tts.xai.language']).toContain('"auto"')
    expect(xh.settings.fieldDescriptions['tts.xai.language']).toContain('pt-BR')
    expect(xh.settings.fieldDescriptions['tts.xai.bitRate']).toContain('mp3')
    expect(xh.settings.fieldDescriptions['updates.nonInteractiveLocalChanges']).toContain('stash')
    expect(xh.settings.fieldDescriptions['updates.nonInteractiveLocalChanges']).toContain('discard')
    expect(xh.settings.fieldDescriptions.fallbackProviders).toContain('provider:model')
  })
})
