// Two-series bar chart for new and resolved cases.
//
// Drawn as inline SVG rather than pulled from a charting library: it is one
// chart, and the numbers are already in an accessible table underneath, so the
// chart is a visual summary and not the only way to read the data.
const NEW_COLOUR = "#0d6efd";
const RESOLVED_COLOUR = "#198754";

export function initSeriesChart() {
  const element = document.getElementById("statistics-series");
  if (!element || !element.dataset.series) return;

  let series;
  try {
    series = JSON.parse(element.dataset.series);
  } catch (error) {
    return;
  }
  if (!series.length) return;

  const width = 560;
  const height = 180;
  const padding = { top: 12, right: 8, bottom: 24, left: 28 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const peak = Math.max(1, ...series.map((point) => Math.max(point.new, point.resolved)));
  const slot = plotWidth / series.length;
  const barWidth = Math.max(2, slot / 2 - 2);

  const bars = series
    .map((point, index) => {
      const x = padding.left + index * slot;
      const newHeight = (point.new / peak) * plotHeight;
      const resolvedHeight = (point.resolved / peak) * plotHeight;
      return `
        <rect x="${x + 1}" y="${padding.top + plotHeight - newHeight}"
              width="${barWidth}" height="${newHeight}" fill="${NEW_COLOUR}"></rect>
        <rect x="${x + barWidth + 2}" y="${padding.top + plotHeight - resolvedHeight}"
              width="${barWidth}" height="${resolvedHeight}" fill="${RESOLVED_COLOUR}"></rect>
      `;
    })
    .join("");

  const labels = series
    .map((point, index) => {
      // Only every other label, otherwise twelve months overlap.
      if (index % 2 !== 0) return "";
      const x = padding.left + index * slot + slot / 2;
      return `<text x="${x}" y="${height - 6}" font-size="9" text-anchor="middle"
                    fill="currentColor" opacity="0.6">${point.label.slice(2)}</text>`;
    })
    .join("");

  element.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" role="img"
         aria-label="New and resolved cases per month">
      <line x1="${padding.left}" y1="${padding.top + plotHeight}"
            x2="${width - padding.right}" y2="${padding.top + plotHeight}"
            stroke="currentColor" opacity="0.2"></line>
      <text x="0" y="${padding.top + 8}" font-size="9" fill="currentColor"
            opacity="0.6">${peak}</text>
      ${bars}
      ${labels}
    </svg>
  `;
}
