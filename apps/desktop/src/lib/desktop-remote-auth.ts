// Upstream-Derived: apps/desktop/src/lib/desktop-remote-auth.ts @ 7dd2b2dc7 (MIT)
import type { DesktopAuthProvider } from '@/global'

export interface RemoteAuthProviderShape {
  isPassword: boolean
  providerLabel: string
}

function providerDisplayName(provider: DesktopAuthProvider): string {
  return provider.displayName || provider.name
}

export function deriveRemoteAuthProviderShape(
  providers: DesktopAuthProvider[] | null | undefined,
  fallback = 'your identity provider'
): RemoteAuthProviderShape {
  const list = providers ?? []

  if (list.length === 0) {
    return { isPassword: false, providerLabel: fallback }
  }

  return {
    isPassword: list.every(provider => Boolean(provider.supportsPassword)),
    providerLabel: list.map(providerDisplayName).join(' / ')
  }
}
