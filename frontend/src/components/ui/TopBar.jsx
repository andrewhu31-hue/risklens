// The wordmark and account actions, shared by every signed-in page.
export function Wordmark({ size = "sm", className = "text-ink" }) {
  const big = size === "lg";
  return (
    <span className={`inline-flex items-center gap-2 font-semibold ${className} ${big ? "text-2xl" : "text-[15px]"}`}>
      <svg
        viewBox="0 0 20 20"
        className={big ? "h-6 w-6" : "h-[18px] w-[18px]"}
        aria-hidden="true"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
      >
        <circle cx="10" cy="10" r="8.2" />
        <path d="M2.5 13.2 6.6 9.4l3 2.4 3.6-4.6 4.4 2.8" strokeLinejoin="round" strokeLinecap="round" />
      </svg>
      RiskLens
    </span>
  );
}

export default function TopBar({ children }) {
  return (
    <header className="border-b border-rule bg-panel">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between gap-4">
        <Wordmark />
        <div className="flex items-center gap-2">{children}</div>
      </div>
    </header>
  );
}
