import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import ts from 'typescript'

const source = await readFile(new URL('../src/utils/pronunciation.ts', import.meta.url), 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText
const { alignWords } = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`)
assert.deepEqual(alignWords('I like hot tea', 'I like tea').map(w => w.score), [100, 100, 0, 100])
assert.deepEqual(alignWords('very very good', 'very good').map(w => w.score).sort(), [0, 100, 100])
assert.deepEqual(alignWords('Olá, mundo!', 'olá mundo').map(w => w.score), [100, 100])
assert.equal(alignWords('hello', '')[0].score, 0)
assert.deepEqual(alignWords('', 'hello'), [])
assert.deepEqual(alignWords('a cat', 'a little cat').map(w => w.score), [100, 100])
console.log('6 casos de alinhamento aprovados')
