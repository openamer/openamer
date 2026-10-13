# Product Hunt Edit via Computer-Use — Session Playbook

## Prerequisites
- User logged in to PH within <48h (cookies still valid)
- Browser (Chromium-based Edge/Brave) already open with a PH tab
- No Cloudflare/JS challenge on the current session

## Step-by-step

1. **Find the browser tab**: `capture(app="msedge"|"Brave", mode="som")` → look for `TabItem` containing "Product Hunt" or "Edit Launch"
2. **Activate tab**: `click(element=<tab-index>)` → works in background
3. **Navigate to Edit**: `click(element=<"Edit Launch"|"Edit"> link)` → capture_after
4. **Edit Name**: click name field → ctrl+a → type "OpenAmer" → **capture+verify** (label should show "8/40")
5. **Edit Tagline**: click tagline field → ctrl+a → type → verify (should show "60/60")
6. **Edit Description**: click description field → ctrl+a → type → verify
7. **Save**: click "Save changes" button → capture → verify "All changes saved successfully."

## Traps
- **Name concatenation**: ctrl+a doesn't always clear; verify char count after each field
- **Delete button**: "Delete post" sits near "Save changes" on long pages; verify button label in AX tree before clicking
- **Unsaved changes warning**: before save the page shows "You've got unsaved changes"; after save it becomes "All changes saved successfully."
- **File upload**: impossible via cua-driver (native dialog blocked)