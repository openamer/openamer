import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('..', import.meta.url))
const read = (name) => readFileSync(path.join(root, name))
const mark = read('src/components/brand-mark.tsx').toString()
assert.ok(mark.includes("assetPath('openamer-logo.png')"), 'Setup must render the OpenAmer logo')
assert.ok(!mark.includes('openamer-girl'), 'Setup must not reference the legacy portrait')
const canonical = read('../../docs/assets/openamer-logo.png')
for (const name of ['public/openamer-logo.png', '../desktop/assets/icon.png', '../desktop/public/openamer.png', '../../website/static/img/openamer-logo.png', '../../website/static/img/logo.png']) {
  assert.deepEqual(read(name), canonical, `${name} must ship the canonical O/A monogram`)
}
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
    assert.equal(bytes.readUInt16LE(4), 7, 'Windows icon must include 16 through 256px')
    for (let i = 0; i < bytes.readUInt16LE(4); i += 1) {
      const entry = 6 + i * 16
      const size = bytes[entry] || 256
      const length = bytes.readUInt32LE(entry + 8)
      const offset = bytes.readUInt32LE(entry + 12)
      assert.ok(offset + length <= bytes.length, 'ICO bitmap must fit in the container')
      assert.equal(bytes.readUInt32LE(offset), 40, 'Use shell-compatible BMP entries')
      assert.equal(bytes.readInt32LE(offset + 4), size)
      assert.equal(bytes.readInt32LE(offset + 8), size * 2)
      assert.equal(bytes.readUInt16LE(offset + 14), 32)
    }
    for (const target of ['../desktop/assets/icon.ico', '../desktop/public/favicon.ico', '../../web/public/favicon.ico', '../../website/static/img/favicon.ico']) assert.deepEqual(read(target), bytes, `${target} must match the native O/A icon`)
  } else if (name.endsWith('.icns')) {
    assert.equal(bytes.subarray(0, 4).toString(), 'icns')
    assert.equal(bytes.readUInt32BE(4), bytes.length)
    let offset = 8
    while (offset < bytes.length) {
      const length = bytes.readUInt32BE(offset + 4)
      assert.ok(length > 8 && offset + length <= bytes.length)
      assert.equal(bytes.subarray(offset + 9, offset + 12).toString(), 'PNG')
      offset += length
    }
    assert.equal(offset, bytes.length)
    assert.deepEqual(bytes, read('../desktop/assets/icon.icns'))
  }
}
assert.deepEqual(read('../../website/static/img/favicon.svg'), read('../../docs/assets/openamer-logo.svg'))
console.log('PASS: shared canonical O/A monogram; PNG dimensions; seven BMP ICO sizes; ICNS container and desktop/setup/web/website parity')
