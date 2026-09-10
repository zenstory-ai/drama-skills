import { continueRender, delayRender } from "remotion";

/**
 * Remotion captures a frame as soon as React has painted. Anything the browser
 * is still fetching — a web font above all — is simply absent from that frame,
 * and nothing downstream reports it: the film measures correct and reads wrong.
 * The documented guard is to hold the render open until the font layer settles.
 */
export const waitForFonts = (): void => {
  const handle = delayRender("等待字体就绪");
  document.fonts.ready.then(
    () => continueRender(handle),
    () => continueRender(handle),
  );
};

/**
 * `document.fonts.ready` only promises that loading has finished, not that the
 * requested family exists. A missing CJK face does not raise anything — the
 * browser silently substitutes, and a whole film ships in the wrong typeface.
 *
 * Measuring is the only reliable test: lay the same characters out in the
 * requested stack and in a family that cannot exist. Identical widths mean
 * nothing in the stack resolved and the substitute is what would be filmed.
 */
let familyChecked = "";

export const assertFamilyResolves = (fontFamily: string, sample: string): void => {
  // The answer cannot change within a render, and this runs on every frame of
  // the film, so it is measured once per family and then skipped.
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
