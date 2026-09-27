import React from "react";
import { Sequence, useVideoConfig } from "remotion";
import { ScreenTextStyle } from "../schema";
import { assertFamilyResolves } from "../font";
import { Card } from "./Card";
import { CornerChip } from "./CornerChip";
import { SystemPanel } from "./SystemPanel";
import { TaskPanel } from "./TaskPanel";
import { SANS, StyleProps } from "./tokens";

/** One component per style; swapping a look never touches parsing or timing. */
const STYLES: Record<ScreenTextStyle, React.FC<StyleProps>> = {
  card: Card,
  system: SystemPanel,
  task: TaskPanel,
  corner: CornerChip,
};

const Checked: React.FC<StyleProps> = ({ text }) => {
  assertFamilyResolves(SANS, text.items.map((item) => item.text).join(""));
  const Style = STYLES[text.style];
  return <Style text={text} />;
};

/** Places one piece in output time; inside it, frame 0 is the piece's first frame. */
export const ScreenTextLayer: React.FC<StyleProps> = ({ text }) => {
  const { fps } = useVideoConfig();
  const from = Math.round(text.start * fps);
  const until = Math.round(text.end * fps);
  if (until <= from) return null;
  return (
    <Sequence from={from} durationInFrames={until - from} layout="none">
      <Checked text={text} />
    </Sequence>
  );
};
