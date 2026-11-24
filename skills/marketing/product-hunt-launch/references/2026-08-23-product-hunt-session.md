# Product Hunt Launch — Session Reference (2026-08-23)

## Launch page URL

```
https://www.producthunt.com/p/github-481/github-d3e5a1af-29c5-4124-b29d-9fa203d91632
```

This is the auto-generated GitHub repo import. The slug `github-481` is the Product Hunt internal ID for the GitHub integration. A manual launch would produce `/p/openamer`.

## Launch status

- Status: **Launched** (August 22nd, 2026 12:01 AM PDT)
- Points: 2
- Followers: 4
- Admin: Damir Sacirovic
- Maker account: `damir sacirovic` + `@openamer`

## AX tree field verification

### Name field

```
Edit 'Name of the launch 8/40' @ (600, 620, 667, 50)
```

**Expected value:** "OpenAmer" (8/40).  
**Broken value seen:** "GitHubOpenAmer" (22/40) — caused by typing "OpenAmer" without first SELECT ALL, leaving the pre-filled "GitHub" concatenated.

### Tagline field

```
Edit 'Tagline 60/60' @ (600, 657, 667, 50)
```

**Correct value:** "Self-improving AI agent: Background Computer-Use & A2A Swarm" (60/60).  
**Overflow value:** 68/60 triggered error text: `"Tagline cannot be longer than 60 characters"`.

### Links field

```
Edit 'Links to the launch' @ (600, 913, 667, 50)
```

Value: `https://github.com/openamer/openamer`

### X account field

```
Edit 'X account of the launch x.com/' @ (684, 1148, 583, 50)
```

**Correct:** type "OpenAmer" (no @ prefix, no x.com/ — those are baked into the label).  
**Broken value seen:** "@launch" — original auto-import value.

### Description field

```
Edit 'Description of the launch 328/500' @ (600, 507, 667, 172)
```

Value: "Self-improving open-source AI agent. Background Computer-Use that doesn't steal your focus. 99+ tools, 127 self-improving skills, A2A agent swarm, 39 autonomous cron jobs, 20+ messaging platforms (Telegram to WhatsApp). Windows-native, no WSL required. VS Code & JetBrains extensions included. 100% open source, MIT license."

### Save confirmation

```
Text 'All changes saved successfully.' @ (910, 1076, 236, 23)
```

**Must be visible after clicking Save.** If `"You've got unsaved changes"` appears instead, save was not committed.

### Sidebar product name

```
Text 'OpenAmer' @ (80, 1095, 87, 24)
```

After name edit. If this still shows "GitHubOpenAmer" (160 chars wide instead of 87), the field was not properly cleared before typing — go back and re-edit.

### Thumbnail preview

```
1. OpenAmer
   Self-improving AI agent: Background Computer-Use & A2A Swarm
```

Shown at position (680, 45, 100, 27) and (680, 75, 589, 27). The "54" label is the PH-internal product ID.

## Media gallery section

Located after the Thumbnail section. Layout:

```
Gallery
The first image will be used as the social preview when your link is shared online.
We recommend at least 3 or more images.

[scroll indicator] [scroll indicator]

[Media button]     [empty slot]   [empty slot]
  75×75             69×69          68×69
```

The `Media` button (element #105, bounds (600, 1276, 75, 75)) triggers a native Windows File Open dialog when clicked. This dialog cannot be automated.

## Key UI element coordinates

All coordinates are on a 1456×864 viewport at 100% scaling:

| Element | AX index | Coords (x, y, w, h) |
|---------|----------|---------------------|
| Name edit field | varies | (600, 620, 667, 50) |
| Tagline edit field | varies | (600, 657, 667, 50) |
| Description edit | varies | (600, 507, 667, 172) |
| Save changes button | varies | (600, 1061, 167, 54) |
| Cancel link | varies | (786, 1061, 105, 54) |
| Delete post button | 197 | (661, 6018, 145, 51) |
| Delete confirm OK | 1 | (1051, 249, 49, 40) |
| Delete confirm Cancel | 2 | (1110, 249, 110, 40) |
| Media upload button | 105 | (600, 1276, 75, 75) |
| Left nav Images&Media | 37 | (250, 331, 163, 27) |
| Left nav Main info | 35 | (250, 266, 85, 27) |

Note: AX indices shift based on scroll position. Search by label text, not by index.

## Edge foreground delivery behavior

When `delivery_mode="foreground"` is used on Edge, the first action succeeds but subsequent actions may fail with `foreground_unavailable` because Edge's UWP frame (`Chrome_WidgetWin_1`) changes its HWND after foreground activation.

**Pattern that works:** Always click the target element (not a neutral area) first with foreground, then use `key`/`type` with foreground. This ensures the correct HWND is tracked.

## Tags configuration

The tag selector is a text input that renders selected tags as pills:
```
Developer Tools [×]  GitHub [×]
```

Clearing and re-adding tags requires clicking the `[×]` on each pill, then typing a new tag and selecting from the dropdown. Pre-filled tags from GitHub import ("Developer Tools", "GitHub") are **sufficient** for the launch — no change needed.

## Makers field

```
Edit 'Makers damir sacirovic damir sacirovic @openamer' @ (600, 4061, 667, 51)
```

Pre-filled from GitHub import. Shows the user's PH profile name twice plus the @handle. No changes needed.

## What a complete PH launch draft looks like

This is the verified field-set after a successful save:

- **Name:** OpenAmer
- **Tagline:** Self-improving AI agent: Background Computer-Use & A2A Swarm
- **URL:** https://github.com/openamer/openamer
- **X Account:** x.com/OpenAmer
- **Description:** 328 chars (full feature list)
- **Tags:** Developer Tools, GitHub
- **Makers:** damir sacirovic + @openamer
- **Pricing:** Free (radio selected)
- **Promo code:** 3 months free / PH10OFF / No expiration
- **Screenshots:** 0/6 (manual step — native file dialog limitation)
- **Video:** none
- **Interactive demo:** none
- **Shoutouts:** none