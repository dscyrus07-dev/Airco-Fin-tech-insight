// ESLint flat config — `next lint` was removed in Next 16.
// Uses the official flat-config export from eslint-config-next, pinned to the
// exact installed Next version (16.2.4) so rules match the framework build.
import next from 'eslint-config-next/core-web-vitals'

const config = [
  {
    ignores: [
      '.next/**',
      'node_modules/**',
      'out/**',
      'coverage/**',
      'next-env.d.ts',
      'public/**',
    ],
  },
  ...next,
]

export default config
