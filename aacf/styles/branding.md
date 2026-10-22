# Branding Assets

The human-readable mirror of the token source of truth. Canonical values are authored as W3C Design
Tokens (`design.tokens.json`, colours in OKLCH) and compiled to CSS custom properties + the Tailwind
theme via Style Dictionary — see [`design-system.md`](design-system.md). Never hardcode these values
in components; reference the semantic token variables (HR0/HR8).

## Colours

### Primary Palette — ATEXIS blue
| Name | Hex | Usage |
|------|-----|-------|
| Primary | `#2E74B5` | ATEXIS brand blue — primary actions, active states, logo |
| Primary Light | `#4A8CCB` | Hover states, links |
| Primary Dark | `#245C90` | Pressed states |

### Neutral Palette
| Name | Hex | Usage |
|------|-----|-------|
| Background | `#FFFFFF` | Page background |
| Surface | `#F8FAFC` | Card/panel background |
| Border | `#E2E8F0` | Borders, dividers |
| Text Primary | `#0F172A` | Headings, body text |
| Text Secondary | `#64748B` | Muted text, labels |
| Text Disabled | `#94A3B8` | Disabled elements |

### Semantic Colours
| Name | Hex | Usage |
|------|-----|-------|
| Success | `#16A34A` | Confirmations, completed |
| Warning | `#D97706` | Caution, pending review |
| Error | `#DC2626` | Errors, destructive actions |
| Info | `#2563EB` | Informational messages |

### Tier Colours
| Tier | Hex | Usage |
|------|-----|-------|
| T1 | `#22C55E` | Self-service, low risk |
| T2 | `#3B82F6` | IS-approved, moderate |
| T3 | `#F59E0B` | IS + Data, elevated |
| T4 | `#EF4444` | Production, high risk |

## Fonts
| Type | Font | Weight | Size |
|------|------|--------|------|
| Heading H1 | Inter | 700 | 2rem |
| Heading H2 | Inter | 600 | 1.5rem |
| Heading H3 | Inter | 600 | 1.25rem |
| Body | Inter | 400 | 1rem |
| Small | Inter | 400 | 0.875rem |
| Mono/Code | JetBrains Mono | 400 | 0.875rem |

## Spacing Scale
- xs: 0.25rem (4px)
- sm: 0.5rem (8px)
- md: 1rem (16px)
- lg: 1.5rem (24px)
- xl: 2rem (32px)
- 2xl: 3rem (48px)

## Border Radius
- sm: 0.25rem
- md: 0.375rem
- lg: 0.5rem
- xl: 0.75rem
- full: 9999px

## Design Tokens (CSS Custom Properties)
```css
:root {
  --color-primary: 207 60% 45%;            /* ATEXIS blue #2E74B5 */
  --color-primary-foreground: 210 40% 98%;
  --color-secondary: 210 40% 96.1%;
  --color-secondary-foreground: 222.2 47.4% 11.2%;
  --color-destructive: 0 84.2% 60.2%;
  --color-accent: 210 40% 96.1%;
  --color-muted: 210 40% 96.1%;
  --color-muted-foreground: 215.4 16.3% 46.9%;
  --color-border: 214.3 31.8% 91.4%;
  --radius: 0.5rem;
}
```
