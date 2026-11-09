import json

import pytest

import utils.media_service as media


def test_build_workflow_sets_prompt_seed_and_frames(tmp_path, monkeypatch):
    workflow_path = tmp_path / "api.json"
    workflow_path.write_text(json.dumps({
        "1": {"inputs": {"text": "old"}},
        "2": {"inputs": {"seed": 0}},
        "3": {"inputs": {"length": 1}},
    }), encoding="utf-8")

    monkeypatch.setattr(media, "COMFYUI_WORKFLOW", workflow_path)
    monkeypatch.setattr(media, "COMFYUI_PROMPT_NODE_ID", "1")
    monkeypatch.setattr(media, "COMFYUI_PROMPT_INPUT", "text")
    monkeypatch.setattr(media, "COMFYUI_SEED_NODE_ID", "2")
    monkeypatch.setattr(media, "COMFYUI_SEED_INPUT", "seed")
    monkeypatch.setattr(media, "COMFYUI_FRAMES_NODE_ID", "3")
    monkeypatch.setattr(media, "COMFYUI_FRAMES_INPUT", "length")
    monkeypatch.setattr(media, "VIDEO_FPS", 12)
    monkeypatch.setattr(media, "MAX_VIDEO_SECONDS", 60)

    result = media._build_workflow("A calm forest", 123, 5)

    assert result["1"]["inputs"]["text"] == "A calm forest"
    assert result["2"]["inputs"]["seed"] == 123
    assert result["3"]["inputs"]["length"] == 60


def test_build_workflow_rejects_bad_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MAX_VIDEO_SECONDS", 10)
    with pytest.raises(ValueError, match="Длительность"):
        media._build_workflow("prompt", None, 11)


def test_build_workflow_rejects_missing_node(tmp_path, monkeypatch):
    workflow_path = tmp_path / "api.json"
    workflow_path.write_text(json.dumps({"1": {"inputs": {"text": "old"}}}), encoding="utf-8")
    monkeypatch.setattr(media, "COMFYUI_WORKFLOW", workflow_path)
    monkeypatch.setattr(media, "COMFYUI_PROMPT_NODE_ID", "1")
    monkeypatch.setattr(media, "COMFYUI_PROMPT_INPUT", "text")
    monkeypatch.setattr(media, "COMFYUI_FRAMES_NODE_ID", "99")
    monkeypatch.setattr(media, "VIDEO_FPS", 16)
    monkeypatch.setattr(media, "MAX_VIDEO_SECONDS", 60)

    with pytest.raises(RuntimeError, match="количества кадров"):
        media._build_workflow("prompt", None, 2)
