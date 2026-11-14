// Run `npm run <script> [...args]` from web/ using the true on-disk path case.
// Why: MSYS/Git-Bash make passes a lower-case drive letter ("c:\...") as cwd on Windows, which
// makes Vitest load two copies of itself ("Cannot read properties of undefined (reading 'config')").
import { spawnSync } from 'node:child_process';
import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const webDir = realpathSync.native(fileURLToPath(new URL('..', import.meta.url)));
const [script, ...rest] = process.argv.slice(2);
if (!script) {
  console.error('usage: node scripts/npm-run.mjs <script> [args...]');
  process.exit(2);
}
const quoted = rest.map((a) => (/[\s"]/.test(a) ? JSON.stringify(a) : a));
const result = spawnSync(['npm', 'run', script, ...quoted].join(' '), {
  cwd: webDir,
  stdio: 'inherit',
  shell: true,
  env: { ...process.env, PWD: webDir, INIT_CWD: webDir },
});
process.exit(result.status ?? 1);
