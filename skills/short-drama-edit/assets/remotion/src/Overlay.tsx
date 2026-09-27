import React, { useMemo } from "react";
import { AbsoluteFill } from "remotion";
// Only the weights drawn: Noto Sans SC 700 and 900, JetBrains Mono 800.
import "@fontsource/noto-sans-sc/700.css";
import "@fontsource/noto-sans-sc/900.css";
import "@fontsource/jetbrains-mono/800.css";
import { OverlayProps } from "./schema";
import { useFaces } from "./font";
import { fontLoadPlan } from "./rules.mjs";
import { ScreenTextLayer } from "./screen/ScreenText";
import { Subtitles } from "./Subtitles";

/**
 * One transparent pass: screen text first, subtitles on top, over empty frames.
 * ffmpeg composites the result onto the untouched picture.
 */
export const Overlay: React.FC<OverlayProps> = (props) => {
  const plan = useMemo(
    () => fontLoadPlan(props.cues, props.screenTexts),
    [props.cues, props.screenTexts],
  );
  if (!useFaces(plan)) return null;
  return (
    <AbsoluteFill>
      {props.screenTexts.map((text, index) => (
        <ScreenTextLayer key={index} text={text} />
      ))}
      <Subtitles cues={props.cues} />
    </AbsoluteFill>
  );
};
