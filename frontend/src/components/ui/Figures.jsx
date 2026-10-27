// A ruled strip of key numbers: one sheet, hairline dividers, large numerals.
const TONE = {
  positive: "text-gain",
  negative: "text-loss",
  neutral: "text-ink",
};

export default function Figures({ items, columns = 4 }) {
  const cols = { 2: "md:grid-cols-2", 3: "md:grid-cols-3", 4: "md:grid-cols-4", 5: "md:grid-cols-5" }[columns];
  return (
    <dl className={`panel grid grid-cols-2 ${cols} overflow-hidden`}>
      {items.map(({ label, value, sublabel, tone = "neutral" }) => (
        <div
          key={label}
          className="flex flex-col gap-1 border-rule-soft px-5 py-4 [&:not(:last-child)]:border-b md:[&:not(:last-child)]:border-b-0 md:border-r md:last:border-r-0 md:[&:nth-child(n+5)]:border-t"
        >
          <dt className="text-[13px] text-muted">{label}</dt>
          <dd className={`text-[28px] leading-tight font-semibold tracking-tight tabular-nums ${TONE[tone]}`}>
            {value}
          </dd>
          {sublabel ? <dd className="text-xs text-muted-faint">{sublabel}</dd> : null}
        </div>
      ))}
    </dl>
  );
}
