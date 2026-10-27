import {
  Bar,
  BarChart as RBarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart as RLineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart as RScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

export const COLORS = {
  ink: "#141A24",
  muted: "#5A6372",
  faint: "#8A929F",
  rule: "#EBEDF1",
  data: "#2D47C8",
  gain: "#0E7C55",
  loss: "#B8382A",
};

const axis = { stroke: COLORS.faint, fontSize: 12, tickLine: false, axisLine: { stroke: COLORS.rule } };

// Recharts colours tooltip rows from the series fill, and falls back to black
// for scatter points, so set the text colours explicitly.
const tooltipProps = {
  contentStyle: {
    background: "#FFFFFF",
    border: "1px solid #DCE0E6",
    borderRadius: 6,
    fontSize: 12,
    padding: "8px 10px",
    boxShadow: "0 4px 16px rgba(20, 26, 36, 0.08)",
  },
  labelStyle: { color: COLORS.ink, fontWeight: 600, marginBottom: 2 },
  itemStyle: { color: COLORS.ink, padding: 0 },
};

export function BarChart({ data, xKey, yKey, height = 240, color = COLORS.data, formatValue, name }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} axisLine={false} tickFormatter={formatValue ? (v) => formatValue(v) : undefined} />
        <Tooltip
          {...tooltipProps}
          cursor={{ fill: "rgba(45, 71, 200, 0.06)" }}
          formatter={(v) => [formatValue ? formatValue(v) : v, name || yKey]}
        />
        <Bar dataKey={yKey} fill={color} radius={[2, 2, 0, 0]} maxBarSize={56} />
      </RBarChart>
    </ResponsiveContainer>
  );
}

export function DivergingBarChart({ data, xKey, yKey, height = 240, formatValue, name }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} axisLine={false} tickFormatter={formatValue ? (v) => formatValue(v) : undefined} />
        <Tooltip {...tooltipProps} formatter={(v) => [formatValue ? formatValue(v) : v, name || yKey]} />
        <Bar dataKey={yKey} radius={[2, 2, 0, 0]} maxBarSize={56}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry[yKey] >= 0 ? COLORS.gain : COLORS.loss} />
          ))}
        </Bar>
      </RBarChart>
    </ResponsiveContainer>
  );
}

export function LineChart({ data, xKey, yKey, height = 240, color = COLORS.data, formatValue, name }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RLineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={COLORS.rule} vertical={false} />
        <XAxis dataKey={xKey} {...axis} />
        <YAxis {...axis} axisLine={false} tickFormatter={formatValue ? (v) => formatValue(v) : undefined} />
        <Tooltip {...tooltipProps} formatter={(v) => [formatValue ? formatValue(v) : v, name || yKey]} />
        <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={2} dot={false} />
      </RLineChart>
    </ResponsiveContainer>
  );
}

function FrontierTooltip({ active, payload }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const isCurrent = payload[0].name === "Your portfolio";
  return (
    <div style={tooltipProps.contentStyle}>
      <p style={tooltipProps.labelStyle}>{isCurrent ? "Your portfolio" : "Efficient frontier"}</p>
      <p className="tabular-nums" style={{ color: COLORS.muted }}>
        Volatility <span style={{ color: COLORS.ink }}>{(p.volatility * 100).toFixed(2)}%</span>
      </p>
      <p className="tabular-nums" style={{ color: COLORS.muted }}>
        Return <span style={{ color: COLORS.ink }}>{(p.return * 100).toFixed(2)}%</span>
      </p>
    </div>
  );
}

const pctTick = (v) => `${(v * 100).toFixed(0)}%`;

// The solver returns minimum-variance points for every target return; only the
// part at or above the lowest-volatility point is efficient.
function efficientPart(points) {
  if (!points?.length) return [];
  const minVol = points.reduce((a, b) => (b.volatility < a.volatility ? b : a));
  return points.filter((p) => p.return >= minVol.return - 1e-12).sort((a, b) => a.volatility - b.volatility);
}

export function FrontierScatter({ frontier, current, height = 320 }) {
  const efficient = efficientPart(frontier);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RScatterChart margin={{ top: 12, right: 20, left: 0, bottom: 20 }}>
        <CartesianGrid stroke={COLORS.rule} />
        <XAxis
          type="number"
          dataKey="volatility"
          name="Volatility"
          {...axis}
          tickFormatter={pctTick}
          domain={["auto", "auto"]}
          label={{ value: "Volatility", position: "insideBottom", offset: -12, fill: COLORS.muted, fontSize: 12 }}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="Return"
          {...axis}
          axisLine={false}
          tickFormatter={pctTick}
          domain={["auto", "auto"]}
          label={{ value: "Return", angle: -90, position: "insideLeft", offset: 14, fill: COLORS.muted, fontSize: 12 }}
        />
        <ZAxis range={[36, 36]} />
        <ZAxis zAxisId="you" range={[140, 140]} />
        <Tooltip content={<FrontierTooltip />} cursor={{ stroke: COLORS.faint, strokeDasharray: "3 3" }} />
        <Scatter
          name="Efficient frontier"
          data={efficient}
          fill={COLORS.data}
          line={{ stroke: COLORS.data, strokeWidth: 1.5 }}
          shape="circle"
        />
        {current ? (
          <Scatter name="Your portfolio" data={[current]} fill={COLORS.loss} shape="diamond" legendType="diamond" zAxisId="you" />
        ) : null}
      </RScatterChart>
    </ResponsiveContainer>
  );
}

// Diverging scale: ultramarine for positive correlation, brick red for negative.
function cellStyle(v) {
  if (v == null) return { background: "transparent", color: COLORS.faint };
  const a = Math.min(Math.abs(v), 1);
  const rgb = v >= 0 ? "45, 71, 200" : "184, 56, 42";
  return { background: `rgba(${rgb}, ${0.06 + a * 0.82})`, color: a > 0.55 ? "#FFFFFF" : COLORS.ink };
}

export function CorrelationHeatmap({ tickers, matrix }) {
  return (
    <div className="overflow-x-auto -mx-1 px-1">
      <table className="border-separate border-spacing-[2px] text-xs tabular-nums">
        <thead>
          <tr>
            <th />
            {tickers.map((t) => (
              <th key={t} scope="col" className="px-1 pb-1.5 font-medium text-muted min-w-[56px]">
                {t}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tickers.map((rowTicker, i) => (
            <tr key={rowTicker}>
              <th scope="row" className="pr-3 text-left font-medium text-muted whitespace-nowrap">
                {rowTicker}
              </th>
              {tickers.map((colTicker, j) => {
                const v = matrix[i][j];
                return (
                  <td
                    key={colTicker}
                    className="h-11 min-w-[56px] rounded-[3px] text-center"
                    style={cellStyle(v)}
                    title={`${rowTicker} and ${colTicker}: ${v == null ? "undefined (constant price)" : v.toFixed(2)}`}
                  >
                    {v == null ? "—" : v.toFixed(2)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 flex items-center gap-3 text-xs text-muted">
        <span>−1</span>
        <span
          className="h-2 w-40 rounded-full"
          style={{
            background: "linear-gradient(90deg, rgb(184,56,42), rgba(184,56,42,0.06) 50%, rgba(45,71,200,0.06) 50%, rgb(45,71,200))",
          }}
          aria-hidden="true"
        />
        <span>+1</span>
        <span className="text-muted-faint">Moves together in blue, opposite in red</span>
      </div>
    </div>
  );
}

const yearTick = (d) => (typeof d === "string" ? d.slice(0, 4) : d);
const growthTick = (v) => `${v >= 1 ? "+" : ""}${Math.round((v - 1) * 100)}%`;

function PerformanceTooltip({ active, payload, label, benchmark }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  const fmt = (v) => (v == null ? "—" : `${v >= 1 ? "+" : ""}${((v - 1) * 100).toFixed(1)}%`);
  return (
    <div style={tooltipProps.contentStyle}>
      <p style={tooltipProps.labelStyle}>{label}</p>
      <p className="tabular-nums flex justify-between gap-6" style={{ color: COLORS.muted }}>
        Your portfolio <span style={{ color: COLORS.data, fontWeight: 600 }}>{fmt(p.portfolio)}</span>
      </p>
      {p.benchmark != null && (
        <p className="tabular-nums flex justify-between gap-6" style={{ color: COLORS.muted }}>
          {benchmark} <span style={{ color: COLORS.ink }}>{fmt(p.benchmark)}</span>
        </p>
      )}
      <p className="tabular-nums flex justify-between gap-6" style={{ color: COLORS.muted }}>
        Below previous high <span style={{ color: COLORS.loss }}>{(p.drawdown * 100).toFixed(1)}%</span>
      </p>
    </div>
  );
}

export function PerformanceChart({ series, benchmark, height = 300 }) {
  const ticks = [];
  let lastYear = null;
  for (const p of series) {
    const y = p.date.slice(0, 4);
    if (y !== lastYear) {
      ticks.push(p.date);
      lastYear = y;
    }
  }
  const step = Math.max(1, Math.ceil(ticks.length / 9));
  const shownTicks = ticks.filter((_, i) => i % step === 0);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <RLineChart data={series} syncId="perf" margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.rule} vertical={false} />
          <XAxis dataKey="date" {...axis} ticks={shownTicks} tickFormatter={yearTick} hide />
          <YAxis {...axis} axisLine={false} tickFormatter={growthTick} width={56} domain={["auto", "auto"]} />
          <Tooltip content={<PerformanceTooltip benchmark={benchmark} />} cursor={{ stroke: COLORS.faint }} />
          {series.some((p) => p.benchmark != null) && (
            <Line
              type="linear"
              dataKey="benchmark"
              stroke={COLORS.faint}
              strokeWidth={1.5}
              strokeDasharray="4 3"
              dot={false}
              isAnimationActive={false}
            />
          )}
          <Line type="linear" dataKey="portfolio" stroke={COLORS.data} strokeWidth={2} dot={false} isAnimationActive={false} />
        </RLineChart>
      </ResponsiveContainer>
      <p className="mt-3 mb-1 pl-14 text-xs text-muted">Below previous high</p>
      <ResponsiveContainer width="100%" height={110}>
        <RLineChart data={series} syncId="perf" margin={{ top: 4, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={COLORS.rule} vertical={false} />
          <XAxis dataKey="date" {...axis} ticks={shownTicks} tickFormatter={yearTick} />
          <YAxis
            {...axis}
            axisLine={false}
            width={56}
            tickFormatter={(v) => `${Math.round(v * 100)}%`}
            domain={["dataMin", 0]}
            tickCount={3}
          />
          <Tooltip content={() => null} cursor={{ stroke: COLORS.faint }} />
          <Line type="linear" dataKey="drawdown" stroke={COLORS.loss} strokeWidth={1.25} dot={false} isAnimationActive={false} />
        </RLineChart>
      </ResponsiveContainer>
    </div>
  );
}
