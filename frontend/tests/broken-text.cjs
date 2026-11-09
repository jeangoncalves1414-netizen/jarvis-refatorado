// Texto com acento quebrado (UTF-8 lido como Latin-1, ex.: "LigaÃ§Ã£o") nunca pode chegar à tela.
const assert = require('node:assert/strict')
const { readdirSync, readFileSync } = require('node:fs')
const path = require('node:path')

const BROKEN = /[\u00C3\u00C2][\u0080-\u00BF]|\u00E2\u20AC|\u00EF\u00BF\u00BD|\uFFFD/

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) return sourceFiles(full)
    return /\.(ts|tsx|css)$/.test(entry.name) ? [full] : []
  })
}

// Falha se algum arquivo de frontend/src tiver a sequência de acento quebrado.
function assertSourceHasNoBrokenText() {
  const offenders = []
  for (const file of sourceFiles(path.join(__dirname, '..', 'src'))) {
    readFileSync(file, 'utf8').split('\n').forEach((line, index) => {
      if (BROKEN.test(line)) offenders.push(`${path.relative(path.join(__dirname, '..'), file)}:${index + 1}`)
    })
  }
  assert.deepEqual(offenders, [], 'Texto com acento quebrado no código: ' + offenders.join(', '))
}

// Falha se a tela atual mostrar a sequência de acento quebrado.
async function assertPageHasNoBrokenText(page) {
  const text = await page.evaluate(() => document.body.innerText)
  const match = BROKEN.exec(text)
  assert.equal(match, null, 'Texto com acento quebrado na tela: ' + (match ? text.slice(Math.max(0, match.index - 20), match.index + 20) : ''))
}

module.exports = { assertSourceHasNoBrokenText, assertPageHasNoBrokenText }
