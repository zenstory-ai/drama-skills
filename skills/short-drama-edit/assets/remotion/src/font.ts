import { continueRender, delayRender } from "remotion";
import { FONT_WAIT_MS, familyIsMissing, mustWaitForFonts, settleWithin } from "./rules.mjs";

/**
 * Remotion captures a frame as soon as React has painted, so a web font still
 * being fetched is simply absent from it. The overlay uses installed families
 * only, so normally there is nothing to wait for and no wait is registered;
 * `assertFamilyResolves` is what proves the type is real.
 */
export const waitForFonts = (): void => {
  if (!mustWaitForFonts(document.fonts)) return;
  const handle = delayRender("等待字体就绪", { timeoutInMilliseconds: FONT_WAIT_MS * 2 });
  settleWithin(document.fonts.ready, FONT_WAIT_MS).then(() => continueRender(handle));
};

/**
 * `document.fonts.ready` promises that loading finished, not that the requested
 * family exists — a missing face raises nothing, the browser substitutes, and
 * the film ships in the wrong typeface. Measuring is the only reliable test;
 * the comparison itself lives in `rules.mjs`.
 */
const checked = new Set<string>();

export const assertFamilyResolves = (fontFamily: string, sample: string): void => {
  // Runs on every frame, so measure once per family.
  if (!sample || checked.has(fontFamily)) return;
  const context = document.createElement("canvas").getContext("2d");
  if (!context) return;

  const measure = (stack: string, text: string): number => {
    context.font = `700 64px ${stack}`;
    return context.measureText(text).width;
  };
  if (familyIsMissing(measure, fontFamily, sample)) {
    throw new Error(
      `字体 ${fontFamily} 在渲染环境里一个都没装上，` +
        "画面会落到浏览器的兜底字体。装一款其中的字体，" +
        "或给 render 传一个本机确实有的字体族。",
    );
  }
  checked.add(fontFamily);
};
