import { useStore } from '@nanostores/react'
import { useEffect } from 'react'

import { Backdrop } from './components/backdrop'
import Failure from './routes/failure'
import Progress from './routes/progress'
import Success from './routes/success'
import Welcome from './routes/welcome'
import { $bootstrap, $route, initialize } from './store'

/*
 * App shell — OpenAmer Setup.
 *
 * No header chrome (the OS title bar already says "OpenAmer"; an in-window
 * repeat of the mark + words was redundant slop). What sits behind the screens
 * instead is the Backdrop: two glows and a dot grid, so every step shares one
 * continuous canvas rather than looking like four separate dialogs.
 *
 * Route state lives in a single $route atom — 4 screens, no react-router.
 */
export default function App() {
  const route = useStore($route)
  const bootstrap = useStore($bootstrap)

  useEffect(() => {
    void initialize()
  }, [])

  return (
    <div className="relative flex h-full flex-col overflow-hidden bg-background text-foreground">
      <Backdrop />
      <main className="relative z-10 flex flex-1 flex-col overflow-hidden">
        {route === 'welcome' && <Welcome />}
        {route === 'progress' && <Progress bootstrap={bootstrap} />}
        {route === 'success' && <Success />}
        {route === 'failure' && <Failure bootstrap={bootstrap} />}
      </main>
    </div>
  )
}
