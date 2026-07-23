import { describe, expect, it } from "vitest";

import {
  DESK_CAMERA_DEFAULT,
  DESK_CAMERA_TALK,
  deskCameraPresetForState,
} from "./desk-camera";

describe("deskCameraPresetForState", () => {
  it("uses the default fixed desk framing for resting states", () => {
    expect(deskCameraPresetForState("idle")).toEqual(DESK_CAMERA_DEFAULT);
    expect(deskCameraPresetForState("listening")).toEqual(DESK_CAMERA_DEFAULT);
    expect(deskCameraPresetForState("thinking")).toEqual(DESK_CAMERA_DEFAULT);
    expect(deskCameraPresetForState("working")).toEqual(DESK_CAMERA_DEFAULT);
    expect(deskCameraPresetForState("celebrating")).toEqual(DESK_CAMERA_DEFAULT);
    expect(deskCameraPresetForState("concerned")).toEqual(DESK_CAMERA_DEFAULT);
  });

  it("zooms in for talking and awaiting_approval", () => {
    expect(deskCameraPresetForState("talking")).toEqual(DESK_CAMERA_TALK);
    expect(deskCameraPresetForState("awaiting_approval")).toEqual(DESK_CAMERA_TALK);
  });

  it("the talk preset is closer and tighter than the default", () => {
    expect(DESK_CAMERA_TALK.position[2]).toBeLessThan(DESK_CAMERA_DEFAULT.position[2]);
    expect(DESK_CAMERA_TALK.fov).toBeLessThan(DESK_CAMERA_DEFAULT.fov);
  });
});
