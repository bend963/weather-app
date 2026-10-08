import {
  Big_Shoulders,
  Bricolage_Grotesque,
  Figtree,
  IBM_Plex_Mono,
  IBM_Plex_Sans_Condensed,
  Instrument_Serif,
  Literata,
  Onest,
  Public_Sans,
  Schibsted_Grotesk,
  Spline_Sans_Mono,
  Work_Sans,
} from "next/font/google";

// Fonts for the dashboard styles (see styles.css). None are preloaded: each
// face is only declared, so the browser downloads just the ones the active
// style actually uses. next/font needs literal options, hence the repetition.

const schibsted = Schibsted_Grotesk({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--ff-schibsted",
});
const splineMono = Spline_Sans_Mono({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--ff-spline-mono",
});
const instrumentSerif = Instrument_Serif({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  weight: "400",
  style: ["normal", "italic"],
  variable: "--ff-instrument-serif",
});
const publicSans = Public_Sans({ subsets: ["latin"], display: "swap", preload: false, variable: "--ff-public-sans" });
const bricolage = Bricolage_Grotesque({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  variable: "--ff-bricolage",
});
const figtree = Figtree({ subsets: ["latin"], display: "swap", preload: false, variable: "--ff-figtree" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  weight: ["400", "500", "600"],
  variable: "--ff-plex-mono",
});
const plexCondensed = IBM_Plex_Sans_Condensed({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  weight: ["400", "500", "600"],
  variable: "--ff-plex-condensed",
});
const bigShoulders = Big_Shoulders({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  axes: ["opsz"],
  variable: "--ff-big-shoulders",
});
const workSans = Work_Sans({ subsets: ["latin"], display: "swap", preload: false, variable: "--ff-work-sans" });
const onest = Onest({ subsets: ["latin"], display: "swap", preload: false, variable: "--ff-onest" });
const literata = Literata({
  subsets: ["latin"],
  display: "swap",
  preload: false,
  style: ["italic"],
  variable: "--ff-literata",
});

export const fontVariables = [
  schibsted,
  splineMono,
  instrumentSerif,
  publicSans,
  bricolage,
  figtree,
  plexMono,
  plexCondensed,
  bigShoulders,
  workSans,
  onest,
  literata,
]
  .map((f) => f.variable)
  .join(" ");
