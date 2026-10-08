/** Minimal line icons for sky conditions. Codes come from the API (conditions.py). */

const Sun = () => (
  <g>
    <circle cx="12" cy="12" r="4" />
    {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
      <line key={a} x1="12" y1="2.5" x2="12" y2="4.5" transform={`rotate(${a} 12 12)`} />
    ))}
  </g>
);

const Moon = ({ dx = 0, dy = 0 }: { dx?: number; dy?: number }) => (
  <path transform={`translate(${dx} ${dy})`} d="M15.5 4.5a7 7 0 1 0 4 11.8A6 6 0 0 1 15.5 4.5z" />
);

const Cloud = ({ y = 0 }: { y?: number }) => (
  <path
    transform={`translate(0 ${y})`}
    d="M7 18h10.5a3.5 3.5 0 0 0 .3-7A5 5 0 0 0 8.2 9.6 4.2 4.2 0 0 0 7 18z"
    className="fill-[var(--surface)]"
  />
);

const Drops = ({ heavy = false }: { heavy?: boolean }) => (
  <g className="stroke-rain">
    {(heavy ? [8, 11, 14, 17] : [9, 13, 17]).map((x) => (
      <line key={x} x1={x} y1="19.5" x2={x - 1} y2="22" />
    ))}
  </g>
);

const Flakes = () => (
  <g className="fill-rain stroke-none">
    {[9, 13, 17].map((x) => (
      <circle key={x} cx={x - 0.5} cy="21" r="0.9" />
    ))}
  </g>
);

export function WeatherIcon({ code, size = 24, className = "" }: { code: string; size?: number; className?: string }) {
  let body: React.ReactNode;
  switch (code) {
    case "clear-day":
      body = <Sun />;
      break;
    case "clear-night":
      body = <Moon />;
      break;
    case "mostly-clear-day":
    case "partly-cloudy-day":
      body = (
        <>
          <g transform="translate(-3 -3) scale(0.85)">
            <Sun />
          </g>
          <Cloud y={1} />
        </>
      );
      break;
    case "mostly-clear-night":
    case "partly-cloudy-night":
      body = (
        <>
          <g transform="translate(-4 -3) scale(0.8)">
            <Moon />
          </g>
          <Cloud y={1} />
        </>
      );
      break;
    case "chance-rain":
    case "rain":
      body = (
        <>
          <Cloud y={-3} />
          <Drops />
        </>
      );
      break;
    case "heavy-rain":
      body = (
        <>
          <Cloud y={-3} />
          <Drops heavy />
        </>
      );
      break;
    case "snow":
    case "chance-snow":
      body = (
        <>
          <Cloud y={-3} />
          <Flakes />
        </>
      );
      break;
    default:
      body = <Cloud y={-1} />;
  }
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {body}
    </svg>
  );
}
