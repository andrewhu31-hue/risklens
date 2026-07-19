export default function SectionHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
      {subtitle ? <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p> : null}
    </div>
  );
}
