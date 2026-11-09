# Text-to-video setup

1. Install and start ComfyUI locally.
2. Install a compatible text-to-video model and any custom nodes required by that model.
3. Build and validate a workflow in ComfyUI. It must accept a text prompt, accept a frame count (or equivalent duration control), and produce an MP4, WebM, MOV, or MKV output.
4. Export the workflow using ComfyUI's API-format export. Do not use the normal UI workflow JSON.
5. Save it as `workflows/text_to_video_api.json` or set `COMFYUI_WORKFLOW` to its path.
6. In the exported API JSON, identify the node IDs and input keys for prompt and frame count. Put those in `.env` as `COMFYUI_PROMPT_NODE_ID`, `COMFYUI_PROMPT_INPUT`, `COMFYUI_FRAMES_NODE_ID`, and `COMFYUI_FRAMES_INPUT`.
7. Optional seed support: configure `COMFYUI_SEED_NODE_ID` and `COMFYUI_SEED_INPUT`.
8. Start this application and submit a prompt. Poll the returned job ID at `/media/video/jobs/{job_id}`; download the result from the `video_url` when status is `completed`.

The repository intentionally does not ship a pretend universal workflow: node IDs, model inputs and output nodes depend on the selected ComfyUI model/custom nodes. The API adapter checks the configured inputs and returns a useful error if the workflow does not match.

Generation duration is capped by `MAX_VIDEO_SECONDS` (default 60) to reduce accidental GPU exhaustion. The video model/workflow can impose lower limits. Longer generation is not guaranteed to be fast or continuous; use a model/workflow designed for the desired length and hardware.
