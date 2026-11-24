# RTL/LTR Layout Control Reference

## Implementation Overview
This skill centralizes RTL/LTR sidebar placement logic by:
1. Detecting RTL locales via `RTL_LOCALES` set
2. Computing target sidebar position (`targetFlipped`) based on locale and current `$panesFlipped` state
3. Updating the `$panesFlipped` store to trigger layout re-rendering

## Key Files
- `src/store/layout.ts` - `$panesFlipped` store definition and subscription
- `src/i18n/context.tsx` - `getRuntimeI18nLocale` and `RTL_LOCALES` constant
- `src/components/pane-shell/tree/model.ts` - `mirrorTreeHorizontal` for RTL mirroring
- `references/rtl-ltr-layout-control.md` - this reference file

## Implementation Steps
1. **Add RTL locale detection** in `src/i18n/context.tsx`:
   ```ts
   const RTL_LOCALES = new Set<Locale>(['ar', 'he', 'fa', 'ur', 'dv', 'ps', 'yi', 'ug', 'ks', 'sd']);
   export function isRtlLocale(locale: Locale): boolean {
     return RTL_LOCALES.has(locale);
   }
   ```

2. **Compute target placement** in the layout subscription effect:
   ```ts
   const isRtl = isRtlLocale(getRuntimeI18nLocale());
   const targetFlipped = isRtl ? true : $panesFlipped.get();
   $panesFlipped.set(targetFlipped);
   ```

3. **Update sidebar toggle** to respect flipped state:
   ```ts
   const isSidebarFlipped = $panesFlipped.get();
   // Use isSidebarFlipped to determine left/right placement
   ```

4. **Validate mirroring** in `mirrorTreeHorizontal`:
   ```ts
   export function mirrorTreeHorizontal(root: LayoutNode): LayoutNode {
     if (root.type === 'split' && root.orientation === 'row') {
       root.children = root.children.reverse();
       root.weights = root.weights.reverse();
     }
     return root;
   }
   ```

## Testing Checklist
- [ ] RTL language (Hebráisch) selected → sidebar appears on right
- [ ] LTR language (Deutsch) selected → sidebar appears on left
- [ ] Language switch during active session → sidebar flips immediately
- [ ] Layout preset `quad` respects flipped state
- [ ] `toggleSidebar` respects `$isSidebarFlipped` value
- [ ] No layout regression when switching between RTL/LTR languages

## Common Pitfalls
- Forgetting to update `RTL_LOCALES` when adding new RTL languages
- Updating `$panesFlipped` before locale change takes effect
- Hardcoding left/right values instead of using `$panesFlipped` state
- Not updating sidebar toggle logic to read flipped state
- Overriding layout presets that ignore `targetFlipped` value