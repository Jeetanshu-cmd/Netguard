// Shared geometry for the vertical trace SVG (viewBox 0 0 520 740) and the
// timeline that animates it. Keeping both in one place stops them drifting.
export const W = 520
export const H = 740
export const CX = 260

export const COLORS = {
  accent: '#3b5bff',
  green: '#22c55e',
  red: '#ef4444',
  amber: '#f59e0b',
  dim: '#1c212c',
}

export const Y = {
  pillTop: 18,
  pillBottom: 50,
  table: 118,
  featLabel: 172,
  featRow1: 182,
  featRow2: 212,
  inferTop: 258,
  inferBottom: 282,
  cardTop: 330,
  cardBottom: 422,
  mergeEnd: 462,
  gate: 484,
  alertTop: 536,
  alertBottom: 608,
  outTop: 668,
  outBottom: 704,
}

export const CARD_W = 112
export const CARD_XS = [18, 142, 266, 390]
export const CARD_CX = CARD_XS.map((x) => x + CARD_W / 2)
export const BAR_W = 96

export const GATE_X0 = 60
export const GATE_W = 400

export const CELL = 26
export const CELL_GAP = 4
export const CELL_X0 = (W - (10 * CELL + 9 * CELL_GAP)) / 2

export const GATES = [
  { x: 140, label: '5-TUPLE' },
  { x: 260, label: 'TIMEOUT 5s/30s' },
  { x: 380, label: 'FIN/RST' },
]

export const CLASS_NAMES = ['BENIGN', 'DOS_DDOS', 'PORTSCAN', 'BRUTEFORCE']

export const fanPath = (i) =>
  `M ${CX} ${Y.inferBottom} C ${CX} ${Y.inferBottom + 26}, ${CARD_CX[i]} ${Y.cardTop - 26}, ${CARD_CX[i]} ${Y.cardTop}`

export const mergePath = (i) =>
  `M ${CARD_CX[i]} ${Y.cardBottom} C ${CARD_CX[i]} ${Y.cardBottom + 24}, ${CX} ${Y.mergeEnd - 22}, ${CX} ${Y.mergeEnd}`

// Cubic bezier point, used so the travelling dot follows the drawn curves.
export function bezier(t, [x0, y0], [x1, y1], [x2, y2], [x3, y3]) {
  const u = 1 - t
  const a = u * u * u
  const b = 3 * u * u * t
  const c = 3 * u * t * t
  const d = t * t * t
  return { x: a * x0 + b * x1 + c * x2 + d * x3, y: a * y0 + b * y1 + c * y2 + d * y3 }
}
