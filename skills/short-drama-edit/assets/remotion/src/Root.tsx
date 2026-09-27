import React from "react";
import { Composition } from "remotion";
import { Overlay } from "./Overlay";
import { defaultProps, OverlayProps } from "./schema";

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="Overlay"
      component={Overlay}
      defaultProps={defaultProps}
      // The caller passes the real frame, fps and length through --props; these
      // stand in only when the composition is opened in the studio by hand.
      durationInFrames={Math.max(1, Math.round(defaultProps.durationInSeconds * defaultProps.fps))}
      fps={defaultProps.fps}
      width={defaultProps.width}
      height={defaultProps.height}
      calculateMetadata={({ props }: { props: OverlayProps }) => ({
        durationInFrames: Math.max(1, Math.round(props.durationInSeconds * props.fps)),
        fps: props.fps,
        width: props.width,
        height: props.height,
      })}
    />
  );
};
