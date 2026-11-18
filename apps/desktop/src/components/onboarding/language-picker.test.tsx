import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { OpenAmerConfigRecord } from '@/openamer'

import { I18nProvider } from '../../i18n/context'

import { DesktopLanguagePickerOverlay } from './language-picker'

/*
 * The setup window asks for the language on its first screen and stores the
 * answer in `display.language`. These tests pin the consequence: the desktop's
 * first-run picker must not ask the same question again.
 */
function client(config: OpenAmerConfigRecord) {
  return {
    getConfig: vi.fn().mockResolvedValue(config),
    saveConfig: vi.fn().mockResolvedValue({ ok: true })
  }
}

function renderPicker(config: OpenAmerConfigRecord) {
  return render(
    <I18nProvider configClient={client(config)}>
      <DesktopLanguagePickerOverlay enabled onCompleted={() => undefined} />
    </I18nProvider>
  )
}

describe('DesktopLanguagePickerOverlay', () => {
  afterEach(() => {
    cleanup()
    window.localStorage.clear()
    vi.restoreAllMocks()
  })

  it('asks when nothing has ever chosen a language', async () => {
    renderPicker({})

    await waitFor(() => expect(screen.getByRole('heading', { name: /language/i })).toBeTruthy())
  })

  it('stays closed when the setup window already wrote the language', async () => {
    renderPicker({ display: { language: 'ja' } })

    // Give the provider time to load the config, then assert nothing rendered.
    await waitFor(() => expect(screen.queryByRole('heading', { name: /language/i })).toBeNull())
  })

  it('stays closed when the language was changed in Settings', async () => {
    renderPicker({ display: { language: 'pt-BR' } })

    await waitFor(() => expect(screen.queryByRole('heading', { name: /language/i })).toBeNull())
  })
})
