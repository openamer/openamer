/**
 * Extract every static string literal from ALL desktop locale modules at once.
 * Usage: node scripts/extract_all_locales.js apps/desktop/src/i18n > out.json
 * Emits { "<locale>": { "dotted\u001fpath": "value" } }
 */
const fs = require('fs')
const path = require('path')
const ts = require('typescript')

const dir = process.argv[2] || 'apps/desktop/src/i18n'
const SEP = '\u001f'

function extract(file) {
  const source = ts.createSourceFile(
    file,
    fs.readFileSync(file, 'utf8'),
    ts.ScriptTarget.ES2020,
    true,
    ts.ScriptKind.TS
  )
  const out = {}
  function visit(node, p) {
    if (ts.isPropertyAssignment(node)) {
      const name = ts.isIdentifier(node.name) || ts.isStringLiteral(node.name)
        ? node.name.text
        : null
      if (name === null) return
      const key = p ? p + SEP + name : name
      const init = node.initializer
      if (ts.isObjectLiteralExpression(init)) {
        visit(init, key)
        return
      }
      if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) {
        out[key] = init.text
        return
      }
      return
    }
    ts.forEachChild(node, (child) => visit(child, p))
  }
  visit(source, '')
  return out
}

const result = {}
for (const f of fs.readdirSync(dir)) {
  if (!f.endsWith('.ts')) continue
  const stem = path.basename(f, '.ts')
  if (stem === 'types' || stem === 'catalog' || stem === 'languages' ||
      stem === 'define-locale' || stem === 'plugin-i18n' ||
      stem.endsWith('.test')) continue
  try {
    result[stem] = extract(path.join(dir, f))
  } catch (e) {
    result[stem] = { __error: String(e) }
  }
}
process.stdout.write(JSON.stringify(result))
