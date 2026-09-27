import React from "react";
import { AbsoluteFill, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { Cue } from "./schema";
import { assertFamilyResolves } from "./font";
import { lineEms } from "./rules.mjs";
import { SANS, SUBTITLE } from "./screen/tokens";

/** Splits a line into plain and highlighted runs, earliest keyword first. */
const runs = (text: string, keys: string[]): { text: string; key: boolean }[] => {
  const out: { text: string; key: boolean }[] = [];
  let rest = text;
  while (rest) {
    const hit = keys
      .map((key) => ({ key, at: rest.indexOf(key) }))
      .filter((found) => found.at >= 0)
      .sort((a, b) => a.at - b.at)[0];
    if (!hit) {
      out.push({ text: rest, key: false });
      break;
    }
    if (hit.at) out.push({ text: rest.slice(0, hit.at), key: false });
    out.push({ text: hit.key, key: true });
    rest = rest.slice(hit.at + hit.key.length);
  }
  return out;
};

/**
 * The subtitle layer: Noto Sans SC 900, white or voice-coloured fill over a
 * dark rim drawn beneath it, baseline about a quarter up the frame so the
 * platform's own UI never covers it. Sizes are fractions of frame height.
 */
export const Subtitles: React.FC<{ cues: Cue[] }> = ({ cues }) => {
  const frame = useCurrentFrame();
  const { fps, height, width } = useVideoConfig();
  const now = frame / fps;
  const cue = cues.find((item) => now >= item.start && now < item.end);
  // Checked against a line about to be filmed, so a missing face stops the
  // render on the first subtitle frame rather than after the whole pass.
  assertFamilyResolves(SANS, cue?.text ?? "");
  if (!cue) return null;

  const u = height / 100;
  // One line: long lines are split upstream; what still does not fit shrinks.
  const size = Math.min(u * 4.3, (width * 0.9) / (lineEms(cue.text) * 1.04));
  const age = now - cue.start;
  const pop = spring({ frame: Math.round(age * fps), fps, config: { damping: 12, stiffness: 260, mass: 0.5 } });
  return (
    <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: u * 24 }}>
      <div
        style={{
          fontFamily: SANS,
          fontWeight: 900,
          fontSize: size,
          color: SUBTITLE.fill[cue.kind],
          letterSpacing: size * 0.04,
          textAlign: "center",
          lineHeight: 1.2,
          whiteSpace: "nowrap",
          WebkitTextStroke: `${u * 0.42}px ${SUBTITLE.rim}`,
          paintOrder: "stroke fill",
          textShadow: `0 ${u * 0.25}px ${u * 0.6}px rgba(0,0,0,0.55)`,
          opacity: Math.min(1, age / 0.06),
          transform: `scale(${0.94 + 0.06 * pop})`,
        }}
      >
        {runs(cue.text, cue.keys).map((run, index) =>
          run.key ? (
            <span
              key={index}
              style={{
                color: SUBTITLE.keyword,
                display: "inline-block",
                // A 120 ms pop as the word lands.
                transform: `scale(${1.08 + 0.15 * Math.max(0, 1 - age / 0.12)})`,
              }}
            >
              {run.text}
            </span>
          ) : (
            <span key={index}>{run.text}</span>
          ),
        )}
      </div>
    </AbsoluteFill>
  );
};
