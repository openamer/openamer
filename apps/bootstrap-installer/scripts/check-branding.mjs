import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const read = (name) => readFileSync(path.join(root, name))
const mark = read('src/components/brand-mark.tsx').toString()
assert.ok(mark.includes("assetPath('openamer-logo.png')"), 'Setup must render the OpenAmer logo')
assert.ok(!mark.includes('openamer-girl'), 'Setup must not reference the legacy portrait')
assert.deepEqual(read('public/openamer-logo.png'), read('../../docs/assets/openamer-logo.png'), 'Setup must ship the canonical DNA logo')
const config = JSON.parse(read('src-tauri/tauri.conf.json'))
for (const name of config.bundle.icon) {
  const bytes = read(`src-tauri/${name}`)
  if (name.endsWith('.png')) {
    assert.equal(bytes.subarray(1, 4).toString(), 'PNG')
    const size = name.includes('@2x') ? 256 : Number(path.basename(name).split('x')[0])
    assert.equal(bytes.readUInt32BE(16), size)
    assert.equal(bytes.readUInt32BE(20), size)
  } else if (name.endsWith('.ico')) {
    assert.equal(bytes.readUInt32LE(0), 65536, 'Windows icon must be an ICO resource')
    assert.ok(bytes.readUInt16LE(4) >= 4, 'Windows icon must include small and high-DPI sizes')
    const lastEntry = 6 + (bytes.readUInt16LE(4) - 1) * 16
    const length = bytes.readUInt32LE(lastEntry + 8)
    const offset = bytes.readUInt32LE(lastEntry + 12)
    assert.deepEqual(bytes.subarray(offset, offset + length), read('src-tauri/icons/128x128@2x.png'), 'Windows icon must embed the same DNA image as the high-DPI PNG')
  } else if (name.endsWith('.icns')) {
    assert.equal(bytes.subarray(0, 4).toString(), 'icns')
  }
}
console.log('PASS: updater header uses canonical DNA logo; all configured native icons exist and have valid dimensions/formats')
