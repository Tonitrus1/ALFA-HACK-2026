import { spawn } from 'node:child_process';
import { setTimeout as pause } from 'node:timers/promises';
const scenarios = process.argv.slice(2).length
  ? process.argv.slice(2)
  : ['rfi', 'manual', 'declined', 'network', 'conflict', 'ocr-failed'];
let failed = false;
for (const scenario of scenarios) {
  const env = {
    ...process.env,
    VITE_DEMO_SCENARIO: scenario,
    E2E_SCENARIO: scenario,
    PLAYWRIGHT_BASE_URL: 'http://127.0.0.1:5180',
  };
  console.log(`\nПроверка сценария: ${scenario}`);
  const server = spawn(
    process.execPath,
    ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5180'],
    { env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] },
  );
  let output = '';
  server.stdout.on('data', (d) => (output += d));
  server.stderr.on('data', (d) => (output += d));
  try {
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        const r = await fetch(env.PLAYWRIGHT_BASE_URL);
        if (r.ok) {
          ready = true;
          break;
        }
      } catch {
        /* Ожидаем локальный сервер */
      }
      await pause(200);
    }
    if (!ready) throw new Error('Не удалось запустить Vite: ' + output);
    const result = await new Promise((resolve, reject) => {
      const child = spawn(
        process.execPath,
        [
          'node_modules/@playwright/test/cli.js',
          'test',
          'tests/e2e/edge.spec.ts',
          '--project=desktop',
          `--output=test-results/scenario-${scenario}`,
          '--reporter=list',
        ],
        { env, windowsHide: true, stdio: 'inherit' },
      );
      child.on('error', reject);
      child.on('exit', resolve);
    });
    if (result !== 0) failed = true;
  } catch (error) {
    console.error(error);
    failed = true;
  } finally {
    server.kill();
    await pause(400);
  }
}
process.exitCode = failed ? 1 : 0;
