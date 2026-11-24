# Fork-rebrand: the identity boundary, measured

Session 2026-10-26. Adopted `morluto/rea` (REA, MIT, TypeScript, ~389k stars, #7 on
GitHub) as `openamer/openamer-re`. Scale first: **504,173 LOC** across 2,139 TS
files plus 995 test files — rewriting is not an option, forking is the only honest
path. Every number below was measured, not estimated.

## What the rebrand actually touched

87 files, +449 / −303 lines. Surgical: no whole-file rewrites (`git diff --numstat`
checked for `added ≈ deleted ≈ file length`, the signature of an EOL flip).

Single source of truth is one file — `src/identity.ts`:

```ts
export const PRODUCT_IDENTITY = {
  displayName: "OpenAmer RE",
  packageName: PACKAGE_METADATA.name,     // generated from package.json
  cliBinary: "oare",
  mcpCommand: `npx -y ${PACKAGE_METADATA.name}@${PACKAGE_METADATA.version} mcp`,
  mcpServerKey: "rea",                    // <- deliberately NOT renamed
  skillName: "openamer-reverse-engineer",
  configFileName: "openamer-re.json",
} as const;
```

`scripts/generate-package-metadata.mjs` regenerates the derived module, so
`package.json` + `identity.ts` are the only two files a future rebrand needs.

## The measured cost of renaming the protocol identity

| Change | Effect |
|---|---|
| `mcpServerKey: "openamer-re"` | `dshClientConfiguration.test.ts` **99 green → 54 red**; `registrationRuntimeEnvironmentCli.test.ts` **18 → 15 red** |
| same | `setupClientConfigCleanupOwnership.test.ts` 4 red — uninstall reports *"The rea-named registration is not REA-owned."* |
| `cliBinary: "oare"` only | `Setup.planning.test.ts` progress empty — a fixture registering `["rea","mcp"]` no longer looks like ours |

Root cause each time: production *does* read `PRODUCT_IDENTITY`, but scattered
literals still hardcode the upstream value —
`ClientRegistrationStatus.ts` (`registration.serverName !== "rea"`),
`DshCordisPatch.ts` (`serverName: "rea"`), `Doctor.ts` (`where rea`),
`ClientConfigurationDocument.ts` (`const [executable = "rea", …]`),
`environmentBundle.ts` (Docker `CMD ["rea", …]`). Grep `"rea"` in `src/` excluding
tests: 22 hits, of which ~6 mean *our binary/server* and the rest are provider ids
or `rea.*` predicate namespaces that must stay.

Decision taken: keep `mcpServerKey: "rea"`, keep `cliBinary: "oare"`. The product
surface is ours; the protocol key stays upstream-compatible so no existing user
loses a registration. Documented in `NOTICE.md` under "Identity boundary
(deliberate)".

## Migration compatibility that made the suite green again

```ts
const LEGACY_PACKAGE_NAMES = ["rea-agents"] as const;
const LEGACY_CLI_BINARIES  = ["rea"] as const;

const isLegacyPackageReference = (reference: string): boolean =>
  LEGACY_PACKAGE_NAMES.some((legacy) => {
    if (reference === legacy || reference === `${legacy}@latest`) return true;
    const prefix = `${legacy}@`;
    return reference.startsWith(prefix) && valid(reference.slice(prefix.length)) !== null;
  });
```

Applied at the two decision points in `inspectClientRegistrationCommand`
(package-runner identity and direct-executable identity). Effect: a machine that
had REA installed can repair or uninstall it after switching to the fork.

## Bundled-file-list drift (three consumers, one contract)

Adding `references/openamer-integration.md` to the packaged skill broke:

- installer: `MANAGED_SKILL_FILES` in `SetupSkill.ts` did not include it → installed
  copy lacked the file (`ENOENT` in acceptance);
- conformance ledger: the generator walks the directory, so the manifest digest
  covered 9 files while the test hardcoded 8 → `expected [ {…} ] to deep equally
  contain {…}`;
- doctor: disagreed with both.

Fix: add to the constant **and** make the test derive its list from it
(`[...MANAGED_SKILL_FILES].sort(localeCompare-less comparator)`) so the third copy
cannot drift again. Also regenerate the ledger *after* a rebuild — the ledger reads
the built `skills/` tree, so order matters (`build → artifacts:managed-evidence`).

## Windows build prerequisite that looks like a warning

```
> node scripts/run-exclusive.mjs artifacts node scripts/run-turbo.mjs run artifacts:skills --force
REA Windows native controls are unavailable: Missing packaged Windows native file
native/windows/build/manifest.json (ENOENT). … no native artifact was loaded.
EXIT=1
```

No turbo output at all: `run-exclusive-command.mjs` fails to load the owned-process
supervisor on Windows and exits 1 before spawning the task. Both files are
gitignored build outputs. Remedies, in order of preference:

1. copy `native/windows/build/{manifest.json,rea-windows-x64.node}` from the
   published npm tarball (the error text names exactly this);
2. build them per `native/windows/README.md`;
3. while diagnosing, bypass the wrapper — `node scripts/run-turbo.mjs run compile
   --force` prints the real task output.

Toolchain: `.nvmrc` pins 24.22.1 and `.npmrc` sets `engine-strict=true`, so a
24.18 runtime gets `EBADENGINE` and `npm install` aborts. Portable fix used:
download `nodejs.org/dist/v24.22.1/node-v24.22.1-win-x64.zip`, unpack to a tools
dir, put that absolute `node.exe` in the MCP `--command`.

## MCP registration with bounded context

229 tools unscoped is unusable. `REA_MCP_TOOL_FAMILIES` is a startup-read,
comma-separated subset of 18 family ids; measured counts via `oare mcp doctor`:

| families | tools |
|---|---|
| unset | 229 |
| direct,enhanced,native,artifact,managed,browser,electron,javascript-runtime,application,session | 179 |
| …without native,enhanced | 132 |
| session,application,electron,javascript-runtime,artifact,managed | **79** (registered) |
| session,application,electron,javascript-runtime | 49 |

`openamer mcp add \<name> --env REA_MCP_TOOL_FAMILIES=… --command \<abs node> --args
\<repo>/scripts/rea.mjs mcp` prompts for tool approval; pipe `y` on stdin when
headless. Verify with `openamer mcp test <name>` → `✓ Connected / ✓ Tools
discovered: 79`.

## What the fork genuinely added

`scripts/openamer_re_bridge.py` in the OpenAmer home turns one Evidence record (or
a bundle, or a JSONL stream with progress lines) into an episode via
`longterm_memory.add_episode(kind="re_finding")`, carrying `evidence_id`,
`subject_sha256`, `confidence`, `authority` and the limitation count — so a later
recall cannot mistake a bounded derivation for a complete one. That is the part no
other REA consumer has, and it is the only part worth calling "ours" beyond naming.
