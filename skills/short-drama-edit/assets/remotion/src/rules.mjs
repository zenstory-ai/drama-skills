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

const EMOJI_GLYPH_RE = /\p{Extended_Pictographic}|\p{Emoji_Presentation}/u;

/** True when `ch` is a printable ASCII character covered by bundled Latin/mono faces. */
export const isAsciiPrintable = (/** @type {string} */ ch) => {
  const cp = ch.codePointAt(0);
  return cp !== undefined && cp >= 0x20 && cp <= 0x7e;
};

/**
 * True only for characters inside the bundled Noto Sans SC CJK/ASCII/punctuation
 * unicode ranges. Other scripts (Cyrillic, Arabic, Hangul, Thai, etc.), Emoji,
 * and control characters return false so the browser falls back cleanly to system
 * faces instead of aborting the render.
 */
export const isCheckableBmpGlyph = (/** @type {string} */ ch) => {
  const cp = ch.codePointAt(0);
  if (cp === undefined || cp <= 0x1f || (cp >= 0x7f && cp <= 0x9f)) return false;
  if (cp > 0xffff) return false;
  if (cp >= 0xd800 && cp <= 0xdfff) return false;
  if (cp === 0x200d || cp === 0x20e3 || (cp >= 0xfe00 && cp <= 0xfe0f)) return false;
  if (EMOJI_GLYPH_RE.test(ch)) return false;
  if (cp >= 0x0020 && cp <= 0x007e) return true;
  if (cp >= 0x00a0 && cp <= 0x00ff) return true;
  if (cp >= 0x2000 && cp <= 0x206f && !(cp >= 0x200b && cp <= 0x200f)) return true;
  if (cp >= 0x3000 && cp <= 0x303f) return true;
  if (cp >= 0x3400 && cp <= 0x4dbf) return true;
  if (cp >= 0x4e00 && cp <= 0x9fff) return true;
  if (cp >= 0xf900 && cp <= 0xfaff) return true;
  if (cp >= 0xff00 && cp <= 0xffef) return true;
  return false;
};

/**
 * Which characters each face must have loaded before the first frame.
 *
 * The faces are split by unicode range, and a browser fetches a range only
 * when text in it is laid out -- after the frame has been captured. Asking for
 * every BMP character the film will draw, up front, is what makes frame 0 look
 * like frame 1000, while Emoji and control characters fall back cleanly to
 * system faces without aborting the render.
 *
 * @param {{ text: string }[]} cues
 * @param {{ items: { text: string }[] }[]} screenTexts
 */
export const fontLoadPlan = (cues, screenTexts) => {
  const uniqueBmp = (/** @type {string} */ text) =>
    [...new Set(Array.from(text).filter(isCheckableBmpGlyph))].join("");
  const drawn = uniqueBmp(
    [
      ...cues.map((cue) => cue.text),
      ...screenTexts.flatMap((piece) =>
        piece.items.map((item) => (parseProgress(item.text) ? item.text.replace(/／/g, "/") : item.text)),
      ),
      CHROME_TEXT,
      DIGITS,
    ].join(""),
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

const isFullEm = (/** @type {string} */ ch) => {
  const cp = ch.codePointAt(0) ?? 0;
  return cp > 0x2e7f || cp === 0x2014 || cp === 0x2026 || (cp >= 0x2018 && cp <= 0x201d);
};

/** Width of a line in ems: CJK, full-width forms, and Chinese dashes/ellipses/curly quotes are one, the rest a little over half. */
export const lineEms = (/** @type {string} */ text) =>
  Array.from(text).reduce((sum, ch) => sum + (isFullEm(ch) ? 1 : 0.58), 0);

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
  const found = text.match(/^\s*([0-9][0-9,]*)\s*[/／]\s*([0-9][0-9,]*)\s*$/);
  if (!found) return null;
  const done = Number(found[1].replace(/,/g, ""));
  const total = Number(found[2].replace(/,/g, ""));
  if (!(total > 0)) return null;
  return { done, total, ratio: Math.min(1, Math.max(0, done / total)) };
};

/**
 * Split a task panel's items into `{ title, goal, progressItem, progress, rewards }`
 * by extracting the `N / M` progress item across `items.slice(1)` first so a
 * 2-item `标题｜0 / 100` renders its progress bar instead of consuming it as `goal`.
 *
 * @template {{ text: string }} T
 * @param {T[]} items
 */
export const splitTaskItems = (items) => {
  const [title] = items;
  const tail = items.slice(1);
  const progressItem = tail.find((item) => parseProgress(item.text)) ?? null;
  const progress = progressItem ? parseProgress(progressItem.text) : null;
  const [goal = null, ...rewards] = tail.filter((item) => item !== progressItem);
  return { title, goal, progressItem, progress, rewards };
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

// ---------------------------------------------------------------- layout & cards

/** Subtitle bottom offset in `u` (percent of frame height): 9% on landscape, 24% on portrait. */
export const subtitleBottomU = (/** @type {number} */ width, /** @type {number} */ height) =>
  width > height ? 9 : 24;

/** Adaptive overlay width cap: preserves portrait ratios while keeping landscape panels compact. */
export const panelWidth = (
  /** @type {number} */ width,
  /** @type {number} */ height,
  /** @type {number} */ widthRatio,
  /** @type {number} */ heightCap,
) => Math.min(width * widthRatio, height * heightCap);

const CJK_CHAR_RE = /[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]/;
const LATIN_CHAR_RE = /[A-Za-z]/;

/**
 * Split a Card row into `{ name, unit, value }`.
 *
 * - `"主号 2"` → `{ name: "主号", unit: "", value: "2" }`
 * - `"主号 粉丝 2"` → `{ name: "主号", unit: "粉丝", value: "2" }`
 * - `"Total Revenue $500"` → `{ name: "Total Revenue", unit: "", value: "$500" }`
 *   (multi-word English/Latin labels stay intact instead of shrinking middle words into a unit)
 *
 * @param {string} row
 */
export const splitCardRow = (row) => {
  const words = row.split(/[\s　]+/).filter(Boolean);
  if (words.length < 2) return { name: row, unit: "", value: "" };
  if (words.length === 2) return { name: words[0], unit: "", value: words[1] };
  const leading = words.slice(0, -1).join(" ");
  if (LATIN_CHAR_RE.test(leading) && !CJK_CHAR_RE.test(leading)) {
    return { name: leading, unit: "", value: words[words.length - 1] };
  }
  return { name: words[0], unit: words.slice(1, -1).join(" "), value: words[words.length - 1] };
};
