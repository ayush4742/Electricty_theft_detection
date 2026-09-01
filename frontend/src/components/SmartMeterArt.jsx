import { Box } from '@mui/material';
import { ink, line, status, surface } from '../theme/tokens';

/**
 * Hero visual: a smart electricity meter, drawn as inline SVG.
 *
 * Chosen over a photograph deliberately. A stock "AI" image would say nothing
 * about metering, and an external URL would make the landing page depend on a
 * host we do not control. This is ~3 KB of markup, needs no network request,
 * scales to any size without blurring, and inherits the monochrome palette so
 * it can never drift from the rest of the interface.
 *
 * The drawing is technical rather than decorative: a meter enclosure, an LCD
 * register showing a reading, a status LED, a nameplate, terminal block, and
 * the service line running to a transmission tower behind it.
 */
const SmartMeterArt = ({ height = 320, ariaLabel = 'Smart electricity meter connected to a distribution network' }) => (
  <Box
    component="svg"
    role="img"
    aria-label={ariaLabel}
    viewBox="0 0 420 340"
    sx={{ width: '100%', height: 'auto', maxHeight: height, display: 'block' }}
  >
    <title>{ariaLabel}</title>

    {/* --- background: distribution line and tower ------------------------ */}
    <g stroke={line.strong} strokeWidth="1.5" fill="none" strokeLinecap="round">
      <path d="M330 40v210" />
      <path d="M300 74h60M306 96h48M314 118h32" />
      <path d="M330 40 300 250M330 40l30 210" />
      <path d="M314 118 346 104M346 118 314 104" />
    </g>
    {/* catenary from the tower down to the service head */}
    <path d="M300 74C258 96 214 104 176 100" stroke={line.strong} strokeWidth="1.5" fill="none" />
    <circle cx="300" cy="74" r="3" fill={ink.muted} />

    {/* --- meter enclosure ------------------------------------------------ */}
    <rect x="42" y="70" width="150" height="210" rx="16"
          fill={surface.card} stroke={ink.primary} strokeWidth="2" />
    {/* service head on top */}
    <path d="M96 70V54a21 21 0 0 1 42 0v16" fill="none" stroke={ink.primary} strokeWidth="2" />
    <circle cx="117" cy="100" r="0" />

    {/* --- LCD register --------------------------------------------------- */}
    <rect x="62" y="92" width="110" height="52" rx="6"
          fill={surface.sunken} stroke={line.strong} strokeWidth="1.5" />
    <text x="164" y="114" textAnchor="end"
          fontFamily="ui-monospace, 'JetBrains Mono', monospace" fontSize="21"
          fontWeight="600" fill={ink.primary} letterSpacing="1.5">
      04821.4
    </text>
    <text x="164" y="133" textAnchor="end"
          fontFamily="ui-monospace, monospace" fontSize="10" fill={ink.secondary} letterSpacing="1">
      kWh · IMPORT
    </text>
    {/* signal bars — the "smart" part: it reports on its own */}
    <g fill={ink.muted}>
      <rect x="70" y="128" width="3" height="5" rx="1" />
      <rect x="76" y="124" width="3" height="9" rx="1" />
      <rect x="82" y="120" width="3" height="13" rx="1" />
    </g>

    {/* --- status LED, labelled so meaning is not carried by colour alone -- */}
    <circle cx="70" cy="164" r="5" fill={status.ok} />
    <text x="84" y="168" fontFamily="inherit" fontSize="11" fill={ink.secondary}>
      REPORTING
    </text>

    {/* --- nameplate ------------------------------------------------------ */}
    <rect x="62" y="182" width="110" height="34" rx="5" fill="none"
          stroke={line.base} strokeWidth="1.5" />
    <text x="72" y="197" fontFamily="inherit" fontSize="10" fontWeight="600" fill={ink.primary}>
      SINGLE PHASE
    </text>
    <text x="72" y="210" fontFamily="ui-monospace, monospace" fontSize="9.5" fill={ink.secondary}>
      240V 10-60A 50Hz
    </text>

    {/* --- terminal block ------------------------------------------------- */}
    <rect x="62" y="228" width="110" height="34" rx="5"
          fill={surface.sunken} stroke={line.base} strokeWidth="1.5" />
    <g fill={ink.muted}>
      <circle cx="80" cy="245" r="4" />
      <circle cx="103" cy="245" r="4" />
      <circle cx="126" cy="245" r="4" />
      <circle cx="149" cy="245" r="4" />
    </g>

    {/* --- service conductors leaving the meter --------------------------- */}
    <g stroke={ink.primary} strokeWidth="2" fill="none" strokeLinecap="round">
      <path d="M80 262v34h180" />
      <path d="M126 262v18" />
    </g>

    {/* --- consumption trace: the thing the model actually reads ---------- */}
    <g transform="translate(232,196)">
      <rect x="0" y="0" width="164" height="100" rx="10"
            fill={surface.card} stroke={line.base} strokeWidth="1.5" />
      <text x="12" y="20" fontFamily="inherit" fontSize="9.5" fontWeight="600"
            fill={ink.secondary} letterSpacing="0.5">
        DAILY CONSUMPTION
      </text>
      {/* a normal profile that drops and stays down — the signature the
          detector is built to notice */}
      <path
        d="M12 66 26 58 40 68 54 54 68 62 82 50 96 60 110 78 124 82 138 76 152 80"
        fill="none" stroke={ink.primary} strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round"
      />
      <circle cx="110" cy="78" r="3.5" fill={surface.card} stroke={status.danger} strokeWidth="2" />
      <line x1="103" y1="42" x2="103" y2="88" stroke={status.danger}
            strokeWidth="1.2" strokeDasharray="3 3" />
      <text x="152" y="40" textAnchor="end" fontFamily="inherit" fontSize="9"
            fontWeight="600" fill={status.danger}>
        sustained drop
      </text>
    </g>
  </Box>
);

export default SmartMeterArt;
