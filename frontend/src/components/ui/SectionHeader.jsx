export default function SectionHeader({ title, subtitle, as: Tag = "h2" }) {
  return (
    <div className="mb-4 max-w-[68ch]">
      <Tag className="text-base font-semibold text-ink">{title}</Tag>
      {subtitle ? <p className="text-sm text-muted mt-1 leading-relaxed">{subtitle}</p> : null}
    </div>
  );
}
