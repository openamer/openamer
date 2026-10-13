import type { Meta, StoryObj } from '@storybook/react-vite'

import { useToast } from '../../hooks/use-toast'
import { Button } from './button'
import { Toast } from './toast'

const meta: Meta<typeof Toast> = {
  component: Toast,
  title: 'Components/Feedback/Toast'
}

export default meta

type Story = StoryObj<typeof Toast>

export const Success: Story = {
  render: () => {
    function Demo() {
      const { showToast, toast } = useToast()

      return (
        <>
          <Button onClick={() => showToast('Operation succeeded', 'success')}>
            Show success toast
          </Button>
          <Toast toast={toast} />
        </>
      )
    }

    return <Demo />
  }
}

export const Error: Story = {
  render: () => {
    function Demo() {
      const { showToast, toast } = useToast()

      return (
        <>
          <Button
            destructive
            onClick={() => showToast('Something went wrong', 'error')}
          >
            Show error toast
          </Button>
          <Toast toast={toast} />
        </>
      )
    }

    return <Demo />
  }
}
