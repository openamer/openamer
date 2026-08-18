import type { ReactNode } from 'react'

import { Cell, Grid } from './components/grid'
import { Progress } from './components/progress'
import { H1 } from './components/typography/h1'
import { Small } from './components/typography/small'

export function BasicPage({ children, subtitle, title }: BasicPageProps) {
  return (
    <>
      <Grid>
        <Cell>
          <Progress value={0} />
        </Cell>
      </Grid>

      <Grid className="lg:grid-cols-[max-content_1fr]">
        <Cell className="-order-1">
          <div className="sticky top-4 flex flex-col gap-4">
            {title ? <H1 className="-mb-2 pr-10 opacity-90">{title}</H1> : null}
            {subtitle ? <Small className="opacity-60">{subtitle}</Small> : null}
          </div>
        </Cell>

        <Cell className="post bg-current/3">{children}</Cell>
      </Grid>
    </>
  )
}

interface BasicPageProps extends React.PropsWithChildren {
  subtitle?: string
  title?: ReactNode
}
