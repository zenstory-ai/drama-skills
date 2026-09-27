import { useEffect, useState } from "react";
import { cancelRender, continueRender, delayRender } from "remotion";
import { FONT_WAIT_MS, familyIsMissing, fontLoadProblem, settleWithin } from "./rules.mjs";

type Plan = { font: string; text: string }[];

/**
 * Holds the first frame until every face in `plan` has the glyphs it will draw.
 *
 * Registered per mount rather than at module load, the way Remotion expects;
 * bounded by `FONT_WAIT_MS`; and a face that is undeclared, fails, or never
 * finishes cancels the render with the reason instead of shipping a fallback.
 * Returns false until then, so nothing is drawn -- or measured -- early; the
 * frame is released only after the ready tree has been committed.
 */
export const useFaces = (plan: Plan): boolean => {
  const [handle] = useState(() => delayRender("加载字体"));
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const loads = Promise.all(plan.map((entry) => document.fonts.load(entry.font, entry.text)));
    settleWithin(loads, FONT_WAIT_MS).then((outcome) => {
      const problem = fontLoadProblem(plan, outcome, (font, text) => document.fonts.check(font, text));
      if (problem) cancelRender(new Error(problem));
      else setReady(true);
    });
  }, [plan]);
  useEffect(() => {
    if (ready) continueRender(handle);
  }, [ready, handle]);
  return ready;
};

/**
 * A second guard at draw time: measuring is the only test of what the frame
 * actually uses, so a stack whose families all fall back stops the render.
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
      `字体 ${fontFamily} 在渲染环境里一个都没有，画面会落到浏览器的兜底字体。` +
        "在 Remotion 工作区运行 npm install 装上字体包。",
    );
  }
  checked.add(fontFamily);
};
