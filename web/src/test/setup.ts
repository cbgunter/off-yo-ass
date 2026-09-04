import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// @testing-library/react's own auto-cleanup only registers itself when it
// finds a global `afterEach` — this project runs with `globals: false`
// (vite.config.ts), so that never fires on its own. Without this,
// multiple `render()` calls across test cases in the same file stack up
// in the DOM instead of resetting between tests.
afterEach(cleanup)
