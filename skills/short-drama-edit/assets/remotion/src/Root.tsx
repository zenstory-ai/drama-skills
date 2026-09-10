import React from "react";
import { Composition } from "remotion";
import { Subtitles } from "./Subtitles";
import { defaultProps, SubtitleProps } from "./schema";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Subtitles"
      component={Subtitles}
      defaultProps={defaultProps}
      // The caller passes the real frame, fps and length through --props; these
      // stand in only when the composition is opened in the studio by hand.
      durationInFrames={Math.max(1, Math.round(defaultProps.durationInSeconds * defaultProps.fps))}
      fps={defaultProps.fps}
      width={defaultProps.width}
      height={defaultProps.height}
      calculateMetadata={({ props }: { props: SubtitleProps }) => ({
        durationInFrames: Math.max(1, Math.round(props.durationInSeconds * props.fps)),
        fps: props.fps,
        width: props.width,
        height: props.height,
      })}
    />
  );
};
