import React from "react";
import { AbsoluteFill } from "remotion";
import { OverlayProps } from "./schema";
import { waitForFonts } from "./font";
import { ScreenTextLayer } from "./screen/ScreenText";
import { Subtitles } from "./Subtitles";

waitForFonts();

/**
 * One transparent pass: screen text first, subtitles on top, over empty frames.
 * ffmpeg composites the result onto the untouched picture.
 */
export const Overlay: React.FC<OverlayProps> = (props) => (
  <AbsoluteFill>
    {props.screenTexts.map((text, index) => (
      <ScreenTextLayer key={index} text={text} fontFamily={props.fontFamily} />
    ))}
    <Subtitles
      cues={props.cues}
      fontScale={props.fontScale}
      bottomScale={props.bottomScale}
      fontFamily={props.fontFamily}
    />
  </AbsoluteFill>
);
