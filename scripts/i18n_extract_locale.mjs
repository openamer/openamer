// Extract a locale file's string table as JSON, losslessly.
//
// The desktop locale files are TypeScript object literals. Regex-parsing them
// is fragile (nested templates, multi-line ternaries, arrays, imported
// constant references). This script walks the TypeScript AST of the file and
// records every property with its initializer *source text*, so nothing is
// lost: a reference to an imported constant stays a reference, a template
// literal stays a template literal.
//
// Output shape:
//   { "locale": "fr",
//     "leaves": [ { "path": "common.apply", "kind": "string",
//                   "text": "Appliquer", "sig": "", "quote": "'" }, ... ] }
//
// kind:
//   string  — a plain string literal
//   func    — an arrow function whose body is a template literal
//   raw     — an arrow function with a non-template body (kept verbatim)
//   array   — an array literal (kept verbatim, element paths are .0, .1, …)
//   ref     — a reference to an imported constant (kept verbatim)

import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const ts = require('typescript')

function findExportObject(sourceFile) {
  for (const stmt of sourceFile.statements) {
    if (!ts.isVariableStatement(stmt)) continue
    for (const decl of stmt.declarationList.declarations) {
      if (!decl.initializer) continue
      let init = decl.initializer
      // unwrap `defineLocale({ ... })`
      if (ts.isCallExpression(init)) {
        const arg = init.arguments[0]
        if (arg && ts.isObjectLiteralExpression(arg)) return { name: decl.name.getText(), obj: arg }
      }
      if (ts.isObjectLiteralExpression(init)) return { name: decl.name.getText(), obj: init }
    }
  }
  throw new Error('no exported object literal found')
}

function unquote(text) {
  // text includes the quotes; strip them and unescape the common cases
  if (text.startsWith("'") && text.endsWith("'")) {
    const body = text.slice(1, -1)
    return body.replace(/\\'/g, "'").replace(/\\\\/g, '\\')
  }
  if (text.startsWith('"') && text.endsWith('"')) {
    return text.slice(1, -1).replace(/\\"/g, '"').replace(/\\\\/g, '\\')
  }
  return null
}

function templateBody(text) {
  // text includes the backticks; strip them, keep ${…} verbatim
  if (text.startsWith('`') && text.endsWith('`')) return text.slice(1, -1)
  return null
}

// Render an arrow function's parameter list exactly as the source has it:
//   count                -> "count"
//   (count: number)      -> "(count: number)"
//   (completed, total)   -> "(completed, total)"
function arrowSignature(init) {
  if (init.parameters.length === 0) return '()'
  const parts = init.parameters.map((p) => {
    if (p.type) return `${p.name.getText()}: ${p.type.getText()}`
    if (p.dotDotDotToken) return `...${p.name.getText()}`
    if (p.initializer) return `${p.name.getText()} = ${p.initializer.getText()}`
    return p.name.getText()
  })
  if (parts.length === 1 && !parts[0].includes(':') && !parts[0].includes('...') && !parts[0].includes('=')) {
    return parts[0]
  }
  return `(${parts.join(', ')})`
}

// Rebuild the plain text of a template literal from its parts. Used for the
// translation table — the writer works from the parts, this is only the
// flat view a translator model can read.
function templateText(parts) {
  let out = ''
  for (const p of parts) {
    if (p.kind === 'head') {
      out += p.text
    } else {
      out += '${' + p.expr + '}' + p.literal
    }
  }
  return out
}

function walk(obj, prefix, out) {
  for (const prop of obj.properties) {
    if (!ts.isPropertyAssignment(prop)) continue
    const name = ts.isIdentifier(prop.name)
      ? prop.name.text
      : ts.isStringLiteral(prop.name)
        ? prop.name.text
        : prop.name.getText()
    const path = prefix ? `${prefix}.${name}` : name
    const init = prop.initializer

    if (ts.isStringLiteral(init)) {
      out.push({
        path,
        kind: 'string',
        text: init.text,
        sig: '',
        quote: init.getText()[0],
      })
      continue
    }

    if (ts.isNoSubstitutionTemplateLiteral(init)) {
      out.push({ path, kind: 'string', text: init.text, sig: '', quote: "'" })
      continue
    }

    if (ts.isTemplateExpression(init)) {
      // a template with ${…}: keep the whole head+spans source text
      out.push({
        path,
        kind: 'raw',
        text: init.getText().slice(1, -1),
        sig: '',
        quote: '',
      })
      continue
    }

    if (ts.isArrowFunction(init)) {
      const sig = arrowSignature(init)
      const body = init.body
      if (ts.isTemplateExpression(body) || ts.isNoSubstitutionTemplateLiteral(body)) {
        // The body may contain a NESTED template literal:
        //   ${ms !== null ? ` in ${ms}ms` : ''}
        // The nested backticks have to be escaped when the file is written
        // back, so the writer needs to know where they are. We therefore
        // keep the source text of the body parts instead of re-assembling
        // a plain string.
        const parts = []
        if (ts.isTemplateExpression(body)) {
          parts.push({ kind: 'head', text: body.head.text })
          for (const span of body.templateSpans) {
            parts.push({ kind: 'span', expr: span.expression.getText(), literal: span.literal.text })
          }
        } else {
          parts.push({ kind: 'head', text: body.text })
        }
        out.push({
          path,
          kind: 'func',
          text: templateText(parts),
          sig,
          quote: '',
          parts,
        })
      } else if (ts.isStringLiteral(body)) {
        out.push({ path, kind: 'func', text: body.text, sig, quote: "'" })
      } else {
        out.push({ path, kind: 'raw', text: body.getText(), sig, quote: '' })
      }
      continue
    }

    if (ts.isArrayLiteralExpression(init)) {
      out.push({ path, kind: 'array', text: init.getText(), sig: '', quote: '' })
      init.elements.forEach((el, idx) => {
        if (ts.isStringLiteral(el)) {
          out.push({ path: `${path}.${idx}`, kind: 'string', text: el.text, sig: '', quote: el.getText()[0] })
        } else if (ts.isNoSubstitutionTemplateLiteral(el)) {
          out.push({ path: `${path}.${idx}`, kind: 'string', text: el.text, sig: '', quote: "'" })
        } else {
          out.push({ path: `${path}.${idx}`, kind: 'raw', text: el.getText(), sig: '', quote: '' })
        }
      })
      continue
    }

    if (ts.isObjectLiteralExpression(init)) {
      walk(init, path, out)
      continue
    }

    // identifier reference (e.g. FIELD_LABELS) or anything else
    out.push({ path, kind: 'ref', text: init.getText(), sig: '', quote: '' })
  }
}

const [, , localeFile, outFile] = process.argv
if (!localeFile) {
  console.error('usage: node i18n_extract_locale.mjs <locale.ts> [out.json]')
  process.exit(1)
}

const abs = resolve(localeFile)
const src = readFileSync(abs, 'utf8')
const sf = ts.createSourceFile(abs, src, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
const { name, obj } = findExportObject(sf)
const leaves = []
walk(obj, '', leaves)

const payload = {
  locale: abs.split(/[\\/]/).pop().replace(/\.ts$/, ''),
  exportName: name,
  leaves,
}
const json = JSON.stringify(payload, null, 1)
if (outFile) writeFileSync(resolve(outFile), json, 'utf8')
else console.log(json)
console.error(`extracted ${leaves.length} leaves from ${payload.locale} (export ${name})`)
