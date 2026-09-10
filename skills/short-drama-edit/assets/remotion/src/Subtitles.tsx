import React, { useMemo } from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { Cue, SubtitleProps } from "./schema";
import { assertFamilyResolves, waitForFonts } from "./font";

waitForFonts();

/**
 * A transparent subtitle layer, composited onto untouched picture.
 *
 * Everything here is expressed as a fraction of frame height, so the same
 * numbers hold for 768×1344 and 1080×1920. That is the whole reason this file
 * exists in pixels rather than in an ASS style: the subtitle renderer's own
 * `PlayRes` scaling was applied twice once already, and type three times too
 * large shipped in a sample film.
 */
export const Subtitles: React.FC<SubtitleProps> = ({
  cues,
  fontScale,
  bottomScale,
  fontFamily,
}) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const now = frame / fps;
  const active = cues.find((cue: Cue) => now >= cue.start && now < cue.end);

  const fontSize = height * fontScale;
  // A dark rim on every side keeps white type legible over a bright frame
  // without a caption box, which is what vertical drama expects. It depends
  // only on the frame, so it is built once instead of on each of the
  // film's frames — and it sits above the early return, because a hook may
  // not be skipped on the frames that carry no line.
  const shadow = useMemo(() => {
    const rim = Math.max(2, height * 0.0024);
    return [
      `0 0 ${rim * 3}px rgba(0,0,0,0.85)`,
      `${rim}px ${rim}px 0 rgba(0,0,0,0.92)`,
      `-${rim}px ${rim}px 0 rgba(0,0,0,0.92)`,
      `${rim}px -${rim}px 0 rgba(0,0,0,0.92)`,
      `-${rim}px -${rim}px 0 rgba(0,0,0,0.92)`,
    ].join(", ");
  }, [height]);

  // Checked against a line that is actually about to be filmed, so the render
  // stops on the first subtitle frame rather than after the whole pass.
  assertFamilyResolves(fontFamily, active?.text ?? "");
  if (!active) return null;

  // A short lift on entry reads as the line arriving with the delivery. It is
  // over well before the first syllable ends, so it never delays reading.
  const age = now - active.start;
  const lift = Math.min(1, age / 0.12);
  const eased = 1 - Math.pow(1 - lift, 3);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: height * bottomScale,
        paddingLeft: width * 0.06,
        paddingRight: width * 0.06,
      }}
    >
      <div
        style={{
          fontFamily,
          fontSize,
          fontWeight: 700,
          color: "#ffffff",
          textAlign: "center",
          lineHeight: 1.28,
          letterSpacing: fontSize * 0.02,
          textShadow: shadow,
          opacity: eased,
          transform: `translateY(${(1 - eased) * fontSize * 0.25}px)`,
          // A long line wraps rather than running off the frame — the failure
          // that made the first shipped version unreadable.
          maxWidth: "100%",
          wordBreak: "break-word",
          whiteSpace: "pre-wrap",
        }}
      >
        {active.text}
      </div>
    </AbsoluteFill>
  );
};
