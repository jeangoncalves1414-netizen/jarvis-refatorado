// Sobe o Vite em 127.0.0.1:5174, roda study.smoke.cjs e derruba o Vite no fim.
const { spawn, spawnSync } = require('node:child_process')
const http = require('node:http')
const path = require('node:path')

const frontend = path.resolve(__dirname, '..', '..', '..', 'frontend')
const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--strictPort', '--host', '127.0.0.1', '--port', '5174'], { cwd: frontend, stdio: 'ignore' })

function ping() {
  return new Promise((resolve) => {
    http.get('http://127.0.0.1:5174/', (res) => { res.resume(); resolve(true) }).on('error', () => resolve(false))
  })
}

;(async () => {
  let up = false
  for (let i = 0; i < 60 && !up; i++) {
    up = await ping()
    if (!up) await new Promise((r) => setTimeout(r, 1000))
  }
  console.log('VITE_UP=' + up)
  let code = 1
  if (up) {
    const env = {
      ...process.env,
      PLAYWRIGHT_MODULE: 'C:\\Users\\maria\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages\\playwright\\driver\\package',
      PANEL_TEST_URL: 'http://127.0.0.1:5174',
      PANEL_TEST_OUTPUT: path.resolve(__dirname, 'screenshots'),
    }
    const r = spawnSync(process.execPath, ['tests/study.smoke.cjs'], { cwd: frontend, env, stdio: 'inherit' })
    code = r.status ?? 1
  }
  console.log('SMOKE_EXIT=' + code)
  vite.kill()
  spawnSync('taskkill', ['/PID', String(vite.pid), '/T', '/F'], { stdio: 'ignore' })
  console.log('VITE_STOPPED')
  process.exit(code)
})()
