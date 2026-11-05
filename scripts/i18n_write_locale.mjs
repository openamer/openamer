// Write a desktop locale .ts file from a JSON translation table.
//
// Usage:
//   node i18n_write_locale.mjs <locale.ts> <translations.json>
//
// translations.json: { "path": "translated text", ... }   (flat, dotted paths)
//
// The file is generated from the ENGLISH source structure, so a locale always
// has exactly the same shape as en.ts — that is what makes a locale complete
// rather than partial. Strings the translator has not produced keep their
// English text, so the file stays type-correct and the UI never breaks.
//
// The output keeps the defineLocale() form used by every non-English locale.

import { readFileSync, writeFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const ts = require('typescript')

// ── AST helpers (same shape as the extractor) ───────────────────────────
function findExportObject(sourceFile) {
  for (const stmt of sourceFile.statements) {
    if (!ts.isVariableStatement(stmt)) continue
    for (const decl of stmt.declarationList.declarations) {
      if (!decl.initializer) continue
      let init = decl.initializer
      if (ts.isCallExpression(init)) {
        const arg = init.arguments[0]
        if (arg && ts.isObjectLiteralExpression(arg)) return { name: decl.name.getText(), obj: arg }
      }
      if (ts.isObjectLiteralExpression(init)) return { name: decl.name.getText(), obj: init }
    }
  }
  throw new Error('no exported object literal found')
}

// Escape a JS/TS single-quoted string literal.
function tsString(text, quote = "'") {
  const q = quote === '"' ? '"' : "'"
  const esc = text
    .replace(/\\/g, '\\\\')
    .replace(new RegExp(q, 'g'), '\\' + q)
    .replace(/\n/g, '\\n')
    .replace(/\r/g, '\\r')
  return q + esc + q
}

// Flatten template parts back into a single text.
function flatTemplate(parts) {
  let out = ''
  for (const p of parts) {
    if (p.kind === 'head') out += p.text
    else out += '${' + p.expr + '}' + p.literal
  }
  return out
}

// A template literal body may contain a NESTED template literal, e.g.
//   ${ms !== null ? ` in ${ms}ms` : ''}
// Inside a ${…} expression a backtick starts a nested template literal and
// must NOT be escaped — escaping it there is a syntax error. A backtick
// outside of any ${…} (i.e. plain text of the outer template) has to be
// escaped, because it would otherwise terminate the outer literal.
//
// So the escaping is context aware: we walk the body and track whether we
// are inside an interpolation.
// Escape the plural forms inside a ternary.
//
// The English source contains
//     ${count === 1 ? 'message' : 'messages'}
// The translated version has the same shape, but a translated plural may
// itself contain an apostrophe (Dutch "y's"). Inside a single-quoted
// string literal that apostrophe has to be escaped, otherwise it ends the
// literal and the template does not parse.
//
// Only the string literals that are part of a ternary are touched. A
// literal in the plain text of the template is not escaped — it is
// rendered by the normal string writer.
function escapeTernaryLiterals(text) {
  // find "? '...'" / ": '...'" pairs and escape the content of the quotes
  let out = ''
  let i = 0
  while (i < text.length) {
    const c = text[i]
    if (c === '\\' && i + 1 < text.length) {
      out += c + text[i + 1]
      i += 2
      continue
    }
    if (c === "'") {
      // read the literal up to its closing quote (honouring escapes)
      let j = i + 1
      let content = ''
      let closed = false
      while (j < text.length) {
        if (text[j] === '\\' && j + 1 < text.length) {
          content += text[j] + text[j + 1]
          j += 2
          continue
        }
        if (text[j] === "'") {
          closed = true
          break
        }
        content += text[j]
        j++
      }
      if (closed) {
        // escape the apostrophes inside the content
        out += "'" + content.replace(/'/g, "\\'") + "'"
        i = j + 1
        continue
      }
    }
    out += c
    i++
  }
  return out
}

// Escape only the string literals that belong to a ternary inside an
// interpolation. Everything else is left alone.
function escapeTernariesOnly(expr) {
  // a ternary looks like  <cond> ? 'a' : 'b'
  const re = /(\?|:)\s*'([^']*)'/g
  return expr.replace(re, (m, op, content) => `${op} '${content.replace(/'/g, "\\'")}'`)
}

function escapeTemplateBody(text) {
  // The text is the body of a template literal. Two things need escaping:
  //
  //   1. A backtick in the PLAIN TEXT of the template would terminate the
  //      literal. It has to be escaped.
  //   2. An apostrophe inside a ternary's string literal
  //      (${count === 1 ? 'y' : 'ys'}) would terminate that literal.
  //
  // We walk the text and track whether we are inside an interpolation.
  // Inside an interpolation, only the ternary literals are escaped; a
  // nested template literal keeps its backticks as they are.
  let out = ''
  let depth = 0
  let inExpr = ''
  let braces = 0
  let nestedTemplate = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (c === '\\' && i + 1 < text.length) {
      if (depth > 0) inExpr += c + text[i + 1]
      else out += c + text[i + 1]
      i++
      continue
    }
    if (depth > 0) {
      // inside an interpolation
      if (c === '`') nestedTemplate = !nestedTemplate
      if (!nestedTemplate) {
        if (c === '{') braces++
        if (c === '}') {
          if (braces === 0) {
            depth--
            out += escapeTernariesOnly(inExpr) + c
            inExpr = ''
            continue
          }
          braces--
        }
      }
      inExpr += c
      continue
    }
    if (c === '`') {
      out += '\\`'
      continue
    }
    if (c === '{' && text[i - 1] === '$') {
      depth++
      braces = 0
      nestedTemplate = false
      inExpr = ''
      out += c
      continue
    }
    out += c
  }
  return out
}

function tsKey(key) {
  return /^[A-Za-z_$][A-Za-z0-9_$]*$/.test(key) ? key : tsString(key)
}

// A leaf rendered from the extraction table.
function renderLeaf(kind, text, sig, quote) {
  if (kind === 'string') return tsString(text, quote === '"' ? '"' : "'")
  if (kind === 'func') {
    const sigText = sig || ''
    if (text.includes('${') || text.includes('`')) return `${sigText} => \`${escapeTemplateBody(text)}\``
    return `${sigText} => ${text}`
  }
  return text // raw / ref / array — verbatim
}
function buildTree(obj, translations, prefix, out) {
  for (const prop of obj.properties) {
    if (!ts.isPropertyAssignment(prop)) continue
    const name = ts.isIdentifier(prop.name)
      ? prop.name.text
      : ts.isStringLiteral(prop.name)
        ? prop.name.text
        : prop.name.getText()
    const path = prefix ? `${prefix}.${name}` : name
    const init = prop.initializer

    if (ts.isStringLiteral(init) || ts.isNoSubstitutionTemplateLiteral(init)) {
      const quote = ts.isStringLiteral(init) ? init.getText()[0] : "'"
      out[name] = { __leaf: 'string', text: translations[path] ?? init.text, quote }
      continue
    }

    if (ts.isTemplateExpression(init)) {
      out[name] = { __leaf: 'func', text: translations[path] ?? init.getText().slice(1, -1), sig: '' }
      continue
    }

    if (ts.isArrowFunction(init)) {
      // The signature is copied verbatim from the source so a type
      // annotation (`(percent: number) =>`) survives.
      let sigText
      if (init.parameters.length === 0) {
        sigText = '()'
      } else if (init.parameters.length === 1) {
        const only = init.parameters[0]
        if (only.type) sigText = `(${only.name.getText()}: ${only.type.getText()})`
        else sigText = only.name.getText()
      } else {
        const parts = init.parameters.map((p) =>
          p.type ? `${p.name.getText()}: ${p.type.getText()}` : p.name.getText(),
        )
        sigText = `(${parts.join(', ')})`
      }
      const body = init.body
      if (ts.isTemplateExpression(body) || ts.isNoSubstitutionTemplateLiteral(body)) {
        // Keep the template structure: head text and the expression source
        // of every span. A nested template inside a span keeps its own
        // backticks, which have to be escaped when written back.
        const parts = []
        if (ts.isTemplateExpression(body)) {
          parts.push({ kind: 'head', text: body.head.text })
          for (const span of body.templateSpans) {
            parts.push({ kind: 'span', expr: span.expression.getText(), literal: span.literal.text })
          }
        } else {
          parts.push({ kind: 'head', text: body.text })
        }
        // The translated text replaces the whole body; the parts are only
        // needed when there is no translation (the English fallback).
        const translated = translations[path]
        out[name] = {
          __leaf: 'func',
          text: translated ?? flatTemplate(parts),
          sig: sigText,
          parts: translated ? null : parts,
        }
      } else if (ts.isStringLiteral(body)) {
        out[name] = { __leaf: 'func', text: translations[path] ?? body.text, sig: sigText }
      } else {
        // non-template body: keep it verbatim, but remember the signature so
        // the writer can rebuild `sig => body`
        out[name] = { __leaf: 'raw', text: body.getText(), sig: sigText }
      }
      continue
    }

    if (ts.isArrayLiteralExpression(init)) {
      const items = init.elements.map((el, idx) => {
        const p = `${path}.${idx}`
        if (ts.isStringLiteral(el)) {
          return { __leaf: 'string', text: translations[p] ?? el.text, quote: el.getText()[0] }
        }
        if (ts.isNoSubstitutionTemplateLiteral(el)) {
          return { __leaf: 'string', text: translations[p] ?? el.text, quote: "'" }
        }
        return { __leaf: 'raw', text: el.getText(), sig: '' }
      })
      out[name] = { __leaf: 'array', items }
      continue
    }

    if (ts.isObjectLiteralExpression(init)) {
      const child = {}
      buildTree(init, translations, path, child)
      out[name] = child
      continue
    }

    // A call like defineFieldCopy({ … }) wraps an object literal. The
    // object is the value, the call is just the wrapper — so we unwrap it
    // and keep the wrapper for rendering.
    if (ts.isCallExpression(init) && init.arguments.length === 1
        && ts.isObjectLiteralExpression(init.arguments[0])) {
      const child = {}
      buildTree(init.arguments[0], translations, path, child)
      out[name] = { __leaf: 'wrapped', text: init.expression.getText(), children: child }
      continue
    }

    out[name] = { __leaf: 'raw', text: init.getText(), sig: '' }
  }
}

// Copy the parts of the reference object that the locale does not have yet.
// The locale keeps its own values (including inline field copies), but gains
// the missing sections and keys from en.ts.
function mergeMissing(enObj, tree, translations, prefix) {
  for (const prop of enObj.properties) {
    if (!ts.isPropertyAssignment(prop)) continue
    const name = ts.isIdentifier(prop.name)
      ? prop.name.text
      : ts.isStringLiteral(prop.name)
        ? prop.name.text
        : prop.name.getText()
    const path = prefix ? `${prefix}.${name}` : name
    const init = prop.initializer
    const existing = tree[name]
    if (existing === undefined) {
      // the whole subtree is missing — take it from the reference
      const child = {}
      buildTree({ properties: [prop] }, translations, path, child)
      tree[name] = child[name]
      continue
    }
    if (ts.isObjectLiteralExpression(init) && existing && typeof existing === 'object'
        && existing.__leaf === undefined) {
      mergeMissing(init, existing, translations, path)
    }
  }
}

function render(node, indent) {
  const pad = ' '.repeat(indent)
  const lines = []
  for (const [key, value] of Object.entries(node)) {
    const k = tsKey(key)
    if (value && typeof value === 'object' && value.__leaf === undefined) {
      lines.push(`${pad}${k}: {`)
      lines.push(...render(value, indent + 2))
      lines.push(`${pad}},`)
    } else if (value.__leaf === 'array') {
      lines.push(`${pad}${k}: [`)
      for (const it of value.items) {
        lines.push(`${pad}  ${renderLeaf(it.__leaf, it.text, it.sig, it.quote)},`)
      }
      lines.push(`${pad}],`)
    } else if (value.__leaf === 'wrapped') {
      // a call wrapper around an object literal, e.g. defineFieldCopy({ … })
      lines.push(`${pad}${k}: ${value.text}({`)
      lines.push(...render(value.children, indent + 2))
      lines.push(`${pad}}),`)
    } else if (value.__leaf === 'raw') {
      // A raw leaf may be an arrow body (kind 'raw' with a signature) or a
      // plain reference (kind 'ref'). The extractor records the signature
      // separately, so the arrow form is rebuilt here.
      if (value.sig) {
        lines.push(`${pad}${k}: ${value.sig} => ${value.text},`)
      } else {
        lines.push(`${pad}${k}: ${value.text},`)
      }
    } else {
      lines.push(`${pad}${k}: ${renderLeaf(value.__leaf, value.text, value.sig, value.quote)},`)
    }
  }
  return lines
}

// ── main ────────────────────────────────────────────────────────────────
const [, , localeFile, translationsFile] = process.argv
if (!localeFile || !translationsFile) {
  console.error('usage: node i18n_write_locale.mjs <locale.ts> <translations.json>')
  process.exit(1)
}

const enFile = resolve(localeFile).replace(/[^\\/]+$/, 'en.ts')
const enSrc = readFileSync(enFile, 'utf8')
const enSf = ts.createSourceFile(enFile, enSrc, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
const { obj: enObj } = findExportObject(enSf)
const translations = JSON.parse(readFileSync(resolve(translationsFile), 'utf8'))

// The STRUCTURE comes from the locale file itself when it exists, and from
// en.ts for the sections the locale does not have yet.
//
// Why not always en.ts? Because a locale may carry values that cannot be
// expressed in the translation table — the inline field copy
// (defineFieldCopy({ … })) of zh and de is the example. Rebuilding from
// en.ts would replace it with the imported English constant and the
// settings panel would fall back to English.
const abs = resolve(localeFile)
let baseObj = enObj
let existingSrc = ''
try {
  existingSrc = readFileSync(abs, 'utf8')
  const existingSf = ts.createSourceFile(abs, existingSrc, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  baseObj = findExportObject(existingSf).obj
} catch {
  // no locale file yet — en.ts is the base
}

// The generated file needs the same imports as en.ts when it references an
// imported constant (FIELD_LABELS / FIELD_DESCRIPTIONS). Without them the
// module fails at runtime with "FIELD_LABELS is not defined".
function collectImports(tree) {
  const refs = new Set()
  const scan = (node) => {
    for (const value of Object.values(node)) {
      if (value && typeof value === 'object' && value.__leaf === undefined) {
        scan(value)
      } else if (value && typeof value === 'object' && value.__leaf === 'raw') {
        const m = /^([A-Z_][A-Z0-9_]*)$/.exec(value.text.trim())
        if (m) refs.add(m[1])
      }
    }
  }
  scan(tree)
  return [...refs].sort()
}

const tree = {}
buildTree(baseObj, translations, '', tree)
// Sections the locale does not have yet come from en.ts, so the locale ends
// up with exactly the same shape as the reference.
mergeMissing(enObj, tree, translations, '')

const localeName = abs.split(/[\\/]/).pop().replace(/\.ts$/, '')
// zh-hant -> zhHant
const exportName = localeName.replace(/-(\w)/g, (_, c) => c.toUpperCase())
const imports = collectImports(tree)
// A wrapper call like defineFieldCopy({ … }) needs its own import.
const wrappers = new Set()
;(function scanWrappers(node) {
  for (const value of Object.values(node)) {
    if (value && typeof value === 'object' && value.__leaf === undefined) {
      scanWrappers(value)
    } else if (value && typeof value === 'object' && value.__leaf === 'wrapped') {
      wrappers.add(value.text)
      scanWrappers(value.children)
    }
  }
})(tree)

// A locale with its own field copy imports THAT instead of the English
// constants. The localized module lives in ./field-copy/<locale>.ts.
let fieldCopyImport = null
const localeNameEarly = abs.split(/[\\/]/).pop().replace(/\.ts$/, '')
if (imports.includes('FIELD_LABELS') || imports.includes('FIELD_DESCRIPTIONS')) {
  const local = resolve(abs).replace(/[^\\/]+$/, `field-copy/${localeNameEarly}.ts`)
  if (existsSync(local)) {
    fieldCopyImport = localeNameEarly
  }
}
const header = []
if (fieldCopyImport) {
  header.push(
    `import { FIELD_DESCRIPTIONS, FIELD_LABELS } from './field-copy/${fieldCopyImport}'`,
  )
  header.push('')
} else if (imports.length) {
  header.push(`import { ${imports.join(', ')} } from '@/app/settings/constants'`)
  header.push('')
}
if (wrappers.size) {
  header.push(`import { ${[...wrappers].sort().join(', ')} } from '@/app/settings/field-copy'`)
  header.push('')
}
header.push(`import { defineLocale } from './define-locale'`)
header.push('')
header.push(`// ${localeName} — generated from en.ts by scripts/i18n_write_locale.mjs.`)
header.push(`// Every section of en.ts is present. Strings not yet translated keep their`)
header.push(`// English text so the file stays type-correct and the UI never breaks.`)
header.push(`export const ${exportName} = defineLocale({`)
const footer = ['})', '']

const body = render(tree, 2)
const out = [...header, ...body, ...footer].join('\n')

// SAFETY GATE: never write a file that does not parse. A broken locale
// file breaks the whole app, so a parse error aborts the write and the
// original file stays untouched.
const check = ts.createSourceFile('check.ts', out, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
if (check.parseDiagnostics && check.parseDiagnostics.length) {
  const d = check.parseDiagnostics[0]
  const pos = check.getLineAndCharacterOfPosition(d.start)
  const lines = out.split('\n')
  console.error(`ABORT: generated file has ${check.parseDiagnostics.length} parse error(s)`)
  console.error(`  line ${pos.line + 1}: ${ts.flattenDiagnosticMessageText(d.messageText, ' ')}`)
  console.error(`  > ${lines[pos.line]}`)
  writeFileSync(abs.replace(/\.ts$/, '.broken.ts'), out, 'utf8')
  console.error('  (wrote .broken.ts for debugging)')
  process.exit(2)
}

// Preserve the line endings of the file we are replacing. The repository
// stores most locale files with CRLF; writing LF would rewrite every line
// of every file and bury the real change in the diff.
let eol = '\n'
try {
  const existing = readFileSync(abs, 'utf8')
  if (existing.includes('\r\n')) eol = '\r\n'
} catch {
  // new file — keep LF
}
const finalText = eol === '\r\n' ? out.replace(/\n/g, '\r\n') : out

writeFileSync(abs, finalText, 'utf8')
console.error(`wrote ${abs}: ${body.length} lines (parse OK, eol=${eol === '\r\n' ? 'CRLF' : 'LF'})`)
