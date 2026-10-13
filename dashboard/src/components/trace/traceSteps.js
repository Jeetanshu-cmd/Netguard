// Copy for the 8 trace steps, plus the TraceLog lines derived from a trace.
export const STEPS = [
  {
    key: 'PACKET',
    title: 'A real packet arrives.',
    body: () => 'The sensor sniffs a real interface. Scapy groups packets into bidirectional flows.',
  },
  {
    key: 'FLOW TABLE',
    title: 'Packets become flows.',
    body: () =>
      'A canonical 5-tuple keys each flow. It expires on FIN/RST, a 5 s idle timeout or a 30 s active timeout.',
  },
  {
    key: 'FEATURES',
    title: 'Nineteen numbers per flow.',
    body: () => 'Each expired flow becomes 19 features in the exact order of features.json.',
  },
  {
    key: 'INFERENCE',
    title: 'The model reads the flow.',
    body: () => 'A Random Forest labels every flow in seconds, with a confidence score.',
  },
  {
    key: 'CLASSES',
    title: 'Four classes, one winner.',
    body: () =>
      'The model scores Benign, DoS_DDoS, PortScan and BruteForce. The highest score becomes the label.',
  },
  {
    key: 'CONFIDENCE',
    title: 'Confidence decides.',
    body: (t) =>
      `Only a non-Benign label above ${t.threshold} confidence passes the gate. Everything else is just logged.`,
  },
  {
    key: 'ALERT ENGINE',
    title: 'One alert, not ten thousand.',
    body: () =>
      'Alerts are aggregated per source IP, so an attack shows up building, not as 10,000 popups.',
  },
  {
    key: 'DASHBOARD',
    title: 'Pushed to this screen.',
    body: () => 'The classified flow and any alert are broadcast over WebSocket and stored in SQLite.',
  },
]

const fmt = (n) => n.toFixed(2)

// One log line per step. The "T+" clock is illustrative stage ordering, not a
// measured latency; TraceLog says so.
export function buildTraceLines(trace) {
  const dst = trace.dst_port != null ? `${trace.dst_ip}:${trace.dst_port}` : trace.dst_ip
  const name = trace.label.toUpperCase()
  return [
    { t: '0.000s', text: `sniff ${trace.src_ip} → ${dst}`, tone: 'info' },
    { t: '0.004s', text: 'flow expired · 5-tuple closed', tone: 'ok' },
    { t: '0.011s', text: 'features extracted n=19 order=features.json', tone: 'ok' },
    { t: '0.012s', text: 'RandomForest.predict_proba(flow)', tone: 'info' },
    {
      t: '0.013s',
      text: `label=${trace.label} conf=${fmt(trace.confidence)}`,
      tone: trace.alertTriggered ? 'bad' : 'ok',
    },
    {
      t: '0.013s',
      text: trace.alertTriggered
        ? `${fmt(trace.confidence)} > ${trace.threshold} → gate open`
        : `${name} · gate closed · logged`,
      tone: trace.alertTriggered ? 'bad' : 'ok',
    },
    {
      t: '0.014s',
      text: trace.alertTriggered
        ? `alert (${trace.src_ip}, ${trace.label}) window=30s flows=${trace.flowCount}`
        : 'alert engine: no alert',
      tone: trace.alertTriggered ? 'bad' : 'muted',
    },
    { t: '0.015s', text: 'ws push /ws/flows type=' + (trace.alertTriggered ? 'alert' : 'flow'), tone: 'info' },
  ]
}
