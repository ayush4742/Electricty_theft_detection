/**
 * EnergyGuard design tokens — light monochrome console.
 *
 * One source of truth for every colour. Components import from here instead of
 * hard-coding hex values, so the palette can be changed in one place and cannot
 * drift page by page (which is how the original build ended up with purple in
 * the charts, cyan in the cards and a different blue again in the tables).
 *
 * The look: an off-white page, white panels, a black icon rail, black pill
 * buttons, and generous whitespace. Colour appears only where it carries
 * meaning — theft, watch, normal — so it reads as an operations console rather
 * than a decorated demo.
 *
 * CONTRAST — every value checked against the surface it is used on:
 *
 *   ink.primary   #111111 on white   18.9:1
 *   ink.secondary #5f5f5f on white    6.4:1   (5.6:1 on the page ground)
 *   ink.muted     #8a8a8a on white    3.5:1   (non-text only)
 *   status.danger #c0392b on white    5.4:1
 *   status.warn   #96690a on white    4.9:1
 *   status.ok     #2e7d32 on white    5.1:1
 *   rail icon     #ffffff on #131313 18.6:1
 *
 * All clear WCAG AA.
 */

export const surface = {
  page: '#f0f0f0',        // the ground the panels sit on
  card: '#ffffff',        // panels, tables, chart surfaces
  sunken: '#f6f6f6',      // inputs, table headers, inner tiles
  hover: '#f1f1f1',       // row and control hover
  rail: '#131313',        // the black navigation rail
  railHover: '#232323',
  inverse: '#111111',     // black buttons, emphatic surfaces
};

export const line = {
  subtle: '#efefef',      // table rules, chart grid
  base: '#e2e2e2',        // panel and input borders
  strong: '#d0d0d0',      // hovered / focused borders
};

export const ink = {
  primary: '#111111',
  secondary: '#5f5f5f',
  muted: '#8a8a8a',
  onDark: '#ffffff',      // text and icons on the rail or a black button
  onDarkMuted: '#9a9a9a', // inactive rail icons
};

/**
 * Status colours. The only chromatic values in the interface, deliberately
 * deep enough to clear 4.5:1 on white. Reserved for state — never reused as a
 * chart series colour.
 */
export const status = {
  danger: '#c0392b',      // theft, critical loss, confirmed case
  warning: '#96690a',     // watch list, attention needed
  ok: '#2e7d32',          // normal, cleared, false alarm
  neutral: '#6b6b6b',     // no data, not applicable
};

/** Soft fills for chips and badges. */
export const statusFill = {
  danger: 'rgba(192, 57, 43, 0.10)',
  warning: 'rgba(150, 105, 10, 0.10)',
  ok: 'rgba(46, 125, 50, 0.10)',
  neutral: 'rgba(107, 107, 107, 0.08)',
};

/**
 * Chart series. Black first, then two greys.
 *
 * A third grey light enough to sit apart from the second cannot also clear 3:1
 * against white — that is the arithmetic limit of a greyscale ramp on a light
 * ground. So series 3 carries a dash pattern as well as a lighter tone, and a
 * fourth series is not offered: past three, facet the chart instead.
 */
export const series = ['#111111', '#6e6e6e', '#b0b0b0'];
export const dash = ['0', '0', '5 4'];

export const chart = {
  grid: '#ececec',
  axis: '#8a8a8a',
  marker: '#ffffff',      // white dot with a black ring, as in the reference
  tooltipBg: '#111111',
  tooltipText: '#ffffff',
  reference: '#c4c4c4',
};

/** Radii — the reference is generously rounded. */
export const radius = { sm: 8, md: 12, lg: 16, xl: 22, pill: 999 };

export const statusColour = (key) => status[key] ?? status.neutral;

export default { surface, line, ink, status, statusFill, series, dash, chart, radius };
