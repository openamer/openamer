import { pathToFileURL } from 'node:url';

// returns true if the passed file is being invoked from node,
// not imported (e.g. by a vitest worker, where argv[1] is undefined).
export function isMain(importMetaUrl) {
    const invoked = process.argv[1];
    if (!invoked) return false;
    return importMetaUrl === pathToFileURL(invoked).href;
}
