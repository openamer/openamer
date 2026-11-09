/**
 * Extract every static string literal from a desktop locale module.
 *
 * Usage: node scripts/extract_locale_literals.js apps/desktop/src/i18n/en.ts
 *
 * Emits { "dotted.path": "value", ... } on stdout, only for values that are a
 * plain string literal. Arrow functions and template literals with ${...} are
 * skipped on purpose: they carry expressions that must not be rewritten.
 *
 * Why an AST and not a regex: the earlier regex parser treated `foo: fn({` as
 * an object open, so a nested call swallowed the following properties and
 * produced a catalog with keys at the wrong depth -- caught by tsc, but only
 * after a 35-minute translation run.
 */
const fs = require('fs')
const ts = require('typescript')

const file = process.argv[2]
if (!file) {
  console.error('usage: node extract_locale_literals.js <file.ts>')
  process.exit(2)
}

const source = ts.createSourceFile(
  file,
  fs.readFileSync(file, 'utf8'),
  ts.ScriptTarget.ES2020,
  true,
  ts.ScriptKind.TS
)

const out = {}

// Some keys contain dots themselves: en.ts has { 'keybinds.openPanel': '...' }.
// Joining paths with a dot would split such a key into nested objects, so the
// path separator is a character that cannot appear in a key.
const SEP = '\u001f'

function visit(node, path) {
  if (ts.isPropertyAssignment(node)) {
    const raw = node.name.getText()
    const name = raw.replace(/^['"]|['"]$/g, '')
    const next = path ? `${path}${SEP}${name}` : name
    const init = node.initializer
    if (ts.isObjectLiteralExpression(init)) {
      init.properties.forEach(child => visit(child, next))
      return
    }
    if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) {
      out[next] = init.text
      return
    }
    return
  }
  ts.forEachChild(node, child => visit(child, path))
}

visit(source, '')
process.stdout.write(JSON.stringify(out))
