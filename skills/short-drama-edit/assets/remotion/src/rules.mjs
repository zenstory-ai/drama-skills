// Decisions the overlay makes that do not need a browser. Plain JavaScript so
// the suite's tests can import this file with Node and no build step.

// ---------------------------------------------------------------- fonts

/** The faces the overlay draws with, as `document.fonts.load` names them. */
export const FACES = {
  heavy: '900 16px "Noto Sans SC"',
  bold: '700 16px "Noto Sans SC"',
  mono: '800 16px "JetBrains Mono"',
};

/** Fixed words the panels draw themselves, so their glyphs are loaded too. */
export const CHROME_TEXT = "【系统提示】【新任务】进度传说史诗稀有·";
const DIGITS = "0123456789天:/, ";

/**
 * Which characters each face must have loaded before the first frame.
 *
 * The faces are split by unicode range, and a browser fetches a range only
 * when text in it is laid out -- after the frame has been captured. Asking for
 * every character the film will draw, up front, is what makes frame 0 look
 * like frame 1000.
 *
 * @param {{ text: string }[]} cues
 * @param {{ items: { text: string }[] }[]} screenTexts
 */
export const fontLoadPlan = (cues, screenTexts) => {
  const unique = (/** @type {string} */ text) => [...new Set(Array.from(text))].join("");
  const drawn = unique(
    [...cues.map((cue) => cue.text), ...screenTexts.flatMap((piece) => piece.items.map((item) => item.text)),
      CHROME_TEXT, DIGITS].join(""),
  );
  return [
    { font: FACES.heavy, text: drawn },
    { font: FACES.bold, text: drawn },
    { font: FACES.mono, text: DIGITS },
  ];
};

export const TIMED_OUT = "timed out";

/**
 * What is wrong with a finished load, or null when every face is ready.
 *
 * A face that no stylesheet declares loads as an empty list and raises
 * nothing; the browser would substitute and the film would ship in the wrong
 * typeface. So an empty list is a failure, as is a load that never finished.
 *
 * @param {{ font: string, text: string }[]} plan
 * @param {unknown} outcome what `settleWithin(Promise.all(loads))` resolved to
 * @param {(font: string, text: string) => boolean} check `document.fonts.check`
 */
export const fontLoadProblem = (plan, outcome, check) => {
  if (outcome === TIMED_OUT) return `字体在 ${FONT_WAIT_MS / 1000} 秒内没有加载完：${plan.map((p) => p.font).join("、")}`;
  if (outcome instanceof Error) return `字体加载失败：${outcome.message}`;
  const loaded = /** @type {unknown[][]} */ (outcome);
  const undeclared = plan.filter((_, index) => !loaded[index] || loaded[index].length === 0);
  if (undeclared.length) {
    return `没有声明这些字体（Remotion 工作区的字体包没装？）：${undeclared.map((p) => p.font).join("、")}`;
  }
  const pending = plan.filter((p) => !check(p.font, p.text));
  if (pending.length) return `字体还没就绪：${pending.map((p) => p.font).join("、")}`;
  return null;
};

export const FONT_WAIT_MS = 10000;

/**
 * Resolves with `promise`'s value, its error, or `TIMED_OUT` after `ms` --
 * whichever comes first -- so a load that never settles cannot hold a frame
 * until the whole render times out, and never resolves as if it had succeeded.
 *
 * @param {Promise<unknown>} promise
 * @param {number} ms
 * @returns {Promise<unknown>}
 */
export const settleWithin = (promise, ms) =>
  new Promise((resolve) => {
    const timer = setTimeout(() => resolve(TIMED_OUT), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        resolve(error instanceof Error ? error : new Error(String(error)));
      },
    );
  });

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
 * True when none of the stack's named families resolves.
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

// ---------------------------------------------------------------- text

/** Width of a line in ems: CJK and full-width forms are one, the rest a little over half. */
export const lineEms = (/** @type {string} */ text) =>
  Array.from(text).reduce((sum, ch) => sum + (ch.charCodeAt(0) > 0x2e7f ? 1 : 0.58), 0);

/** Characters of `text` a typewriter shows `elapsed` seconds in, at 35 ms each after `delay`. */
export const typedLength = (/** @type {number} */ elapsed, delay = 0) =>
  Math.max(0, Math.floor((elapsed - delay) / 0.035 + 1e-9));

/**
 * `2 / 1,000,000` → { done: 2, total: 1000000, ratio }, or null when the item is
 * not a progress reading. The ratio is clamped so the bar never overruns.
 *
 * @param {string} text
 */
export const parseProgress = (text) => {
  const found = text.match(/^\s*([0-9][0-9,]*)\s*\/\s*([0-9][0-9,]*)\s*$/);
  if (!found) return null;
  const done = Number(found[1].replace(/,/g, ""));
  const total = Number(found[2].replace(/,/g, ""));
  if (!(total > 0)) return null;
  return { done, total, ratio: Math.min(1, Math.max(0, done / total)) };
};

// ---------------------------------------------------------------- countdown

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

/** Seconds since the displayed digit last changed; drives the per-second pulse. */
export const sinceTick = (/** @type {number} */ countdown, /** @type {number} */ elapsed) => {
  const remaining = countdown - elapsed;
  return Math.ceil(remaining - 1e-6) - remaining;
};

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
