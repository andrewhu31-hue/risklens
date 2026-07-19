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

const AXIS_COLOR = "#64748b";
const GRID_COLOR = "rgba(255,255,255,0.06)";

const tooltipStyle = {
  background: "#0b1220",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 8,
  fontSize: 12,
  color: "#e6ecf5",
};

export function BarChart({ data, xKey, yKey, height = 240, color = "#38bdf8", formatValue }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis dataKey={xKey} stroke={AXIS_COLOR} fontSize={12} tickLine={false} />
        <YAxis stroke={AXIS_COLOR} fontSize={12} tickLine={false} tickFormatter={formatValue} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => (formatValue ? formatValue(v) : v)} />
        <Bar dataKey={yKey} fill={color} radius={[4, 4, 0, 0]} />
      </RBarChart>
    </ResponsiveContainer>
  );
}

export function DivergingBarChart({ data, xKey, yKey, height = 240, formatValue }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RBarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis dataKey={xKey} stroke={AXIS_COLOR} fontSize={12} tickLine={false} />
        <YAxis stroke={AXIS_COLOR} fontSize={12} tickLine={false} tickFormatter={formatValue} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => (formatValue ? formatValue(v) : v)} />
        <Bar dataKey={yKey} radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry[yKey] >= 0 ? "#34d399" : "#f87171"} />
          ))}
        </Bar>
      </RBarChart>
    </ResponsiveContainer>
  );
}

export function LineChart({ data, xKey, yKey, height = 240, color = "#38bdf8", formatValue }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RLineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} vertical={false} />
        <XAxis dataKey={xKey} stroke={AXIS_COLOR} fontSize={12} tickLine={false} />
        <YAxis stroke={AXIS_COLOR} fontSize={12} tickLine={false} tickFormatter={formatValue} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => (formatValue ? formatValue(v) : v)} />
        <Line type="monotone" dataKey={yKey} stroke={color} strokeWidth={2} dot={false} />
      </RLineChart>
    </ResponsiveContainer>
  );
}

export function FrontierScatter({ frontier, current, height = 280 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RScatterChart margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid stroke={GRID_COLOR} />
        <XAxis
          type="number"
          dataKey="volatility"
          name="Volatility"
          stroke={AXIS_COLOR}
          fontSize={12}
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="Return"
          stroke={AXIS_COLOR}
          fontSize={12}
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
        />
        <ZAxis range={[60, 60]} />
        <Tooltip
          contentStyle={tooltipStyle}
          formatter={(v) => `${(v * 100).toFixed(2)}%`}
          cursor={{ strokeDasharray: "3 3" }}
        />
        <Scatter name="Efficient frontier" data={frontier} fill="#38bdf8" line shape="circle" />
        {current ? <Scatter name="Current portfolio" data={[current]} fill="#f472b6" shape="star" /> : null}
      </RScatterChart>
    </ResponsiveContainer>
  );
}

export function CorrelationHeatmap({ tickers, matrix }) {
  const colorFor = (v) => {
    if (v >= 0) {
      const alpha = 0.15 + v * 0.55;
      return `rgba(56, 189, 248, ${alpha})`;
    }
    const alpha = 0.15 + Math.abs(v) * 0.55;
    return `rgba(248, 113, 113, ${alpha})`;
  };

  return (
    <div className="overflow-x-auto">
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: `100px repeat(${tickers.length}, minmax(64px, 1fr))` }}
      >
        <div />
        {tickers.map((t) => (
          <div key={t} className="text-xs text-slate-400 text-center pb-1 font-medium">
            {t}
          </div>
        ))}
        {tickers.map((rowTicker, i) => (
          <div key={rowTicker} className="contents">
            <div className="text-xs text-slate-400 flex items-center font-medium">{rowTicker}</div>
            {tickers.map((colTicker, j) => (
              <div
                key={colTicker}
                className="aspect-square flex items-center justify-center rounded text-xs tabular-nums"
                style={{ background: colorFor(matrix[i][j]) }}
                title={`${rowTicker} vs ${colTicker}: ${matrix[i][j].toFixed(2)}`}
              >
                {matrix[i][j].toFixed(2)}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
