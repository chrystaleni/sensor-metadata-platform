import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App from './App.jsx'

describe('App', () => {
  it('renders the initialized platform and its metadata domains', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: /sensor metadata management platform/i }),
    ).toBeInTheDocument()
    expect(screen.getByText('Frontend initialized')).toBeInTheDocument()
    expect(screen.getByText('Measurements')).toBeInTheDocument()
    expect(screen.getByText('Physical Devices')).toBeInTheDocument()
    expect(screen.getByText('Network Elements')).toBeInTheDocument()
  })
})
