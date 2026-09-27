// Decisions the overlay makes that do not need a browser. Plain JavaScript so
// the suite's tests can import this file with Node and no build step.

const GENERIC_FAMILIES = new Set([
  "serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui", "math",
  "emoji", "fangsong", "ui-serif", "ui-sans-serif", "ui-monospace", "ui-rounded",
]);

/** The named families in a CSS font stack; generic keywords always resolve, so they prove nothing. */
export const namedFamilies = (/** @type {string} */ stack) =>
  stack
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part && !GENERIC_FAMILIES.has(part.replace(/^["']|["']$/g, "").toLowerCase()));

// Latin glyphs in the probe, because a CJK-only probe cannot tell PingFang from
// "nothing installed" on a machine whose CJK fallback is PingFang itself.
const LATIN_PROBE = " Hamburgefonstiv 0123456789";
// Two generic tails that never share Latin glyphs. A family that happens to
// look like one of them still differs from the other.
const PROBE_TAILS = ["serif", "monospace"];

/**
 * True when none of the stack's named families is installed.
 *
 * `measure(stack, text)` returns the rendered width of `text` in that stack.
 * A family that resolves changes the width against at least one tail; only
 * when the stack measures exactly like both bare tails did nothing resolve.
 *
 * @param {(stack: string, text: string) => number} measure
 * @param {string} stack
 * @param {string} sample
 */
export const familyIsMissing = (measure, stack, sample) => {
  const named = namedFamilies(stack);
  if (named.length === 0) return false;
  const text = sample + LATIN_PROBE;
  return PROBE_TAILS.every(
    (tail) => measure(`${named.join(", ")}, ${tail}`, text) === measure(tail, text),
  );
};

/**
 * Whether a frame has to wait for fonts at all. Installed families lay out
 * synchronously; only declared web faces (@font-face) load in the background.
 * The overlay declares none, and waiting anyway is what hung renders: in a
 * render tab with a video beside it, neither `document.fonts.ready` nor a timer
 * fired before the frame timed out.
 *
 * @param {{ size: number, status: string }} fontSet `document.fonts`
 */
export const mustWaitForFonts = (fontSet) => fontSet.size > 0 && fontSet.status !== "loaded";

/**
 * Resolves when `promise` settles or after `ms`, whichever comes first, so a
 * web face that never finishes loading cannot hold a frame forever.
 *
 * @param {Promise<unknown>} promise
 * @param {number} ms
 * @returns {Promise<void>}
 */
export const settleWithin = (promise, ms) =>
  new Promise((resolve) => {
    const timer = setTimeout(resolve, ms);
    const finish = () => {
      clearTimeout(timer);
      resolve(undefined);
    };
    promise.then(finish, finish);
  });

export const FONT_WAIT_MS = 3000;

/**
 * Whole seconds still showing `elapsed` seconds after a countdown that read
 * `countdown` at its first frame. Rounded up, as a timer reads: it shows its
 * starting value for the whole first second. A pure function of the frame, so
 * every render of the same frame shows the same digits.
 *
 * @param {number} countdown
 * @param {number} elapsed
 */
export const secondsLeft = (countdown, elapsed) =>
  Math.max(0, Math.ceil(countdown - elapsed - 1e-6));

const two = (/** @type {number} */ n) => String(n).padStart(2, "0");

/** `4天 23:59:58`, `01:05:00` or `00:42`, by the largest unit still in play. */
export const formatCountdown = (/** @type {number} */ seconds) => {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  if (days > 0) return `${days}天 ${two(hours)}:${two(minutes)}:${two(rest)}`;
  if (hours > 0) return `${two(hours)}:${two(minutes)}:${two(rest)}`;
  return `${two(minutes)}:${two(rest)}`;
};
