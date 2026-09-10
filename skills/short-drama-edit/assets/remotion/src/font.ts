import { continueRender, delayRender } from "remotion";

/**
 * Remotion captures a frame as soon as React has painted, so a font still being
 * fetched is simply absent from it. Nothing downstream reports that: the film
 * measures correct and reads wrong.
 */
export const waitForFonts = (): void => {
  const handle = delayRender("等待字体就绪");
  document.fonts.ready.then(
    () => continueRender(handle),
    () => continueRender(handle),
  );
};

/**
 * `document.fonts.ready` promises that loading finished, not that the requested
 * family exists — a missing face raises nothing, the browser substitutes, and
 * the film ships in the wrong typeface. Measuring is the only reliable test:
 * identical widths against a family that cannot exist mean nothing resolved.
 */
let familyChecked = "";

export const assertFamilyResolves = (fontFamily: string, sample: string): void => {
  // Runs on every frame, so measure once per family.
  if (!sample || familyChecked === fontFamily) return;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return;

  const measure = (family: string): number => {
    context.font = `700 64px ${family}`;
    return context.measureText(sample).width;
  };
  // A name no font can carry, so it always lands on the browser's last resort.
  const fallbackOnly = measure('"__no_such_family__"');
  const requested = measure(`${fontFamily}, "__no_such_family__"`);
  if (requested === fallbackOnly) {
    throw new Error(
      `字幕字体 ${fontFamily} 在渲染环境里一个都没装上，` +
        "画面会落到浏览器的兜底字体。装一款其中的字体，" +
        "或给 render 传一个本机确实有的字体族。",
    );
  }
  familyChecked = fontFamily;
};
