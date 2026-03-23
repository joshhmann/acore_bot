from __future__ import annotations

import json

import pytest

from tools.file_ops import tool_file_list, tool_file_read, tool_file_write


@pytest.mark.asyncio
async def test_file_read_within_root_passes(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("hello", encoding="utf-8")

    output = await tool_file_read(
        {"project_root": str(tmp_path), "path": "notes.txt", "max_chars": 100}
    )
    payload = json.loads(output)

    assert payload["path"] == "notes.txt"
    assert payload["content"] == "hello"
    assert payload["truncated"] is False


@pytest.mark.asyncio
async def test_file_read_path_traversal_denied(tmp_path):
    with pytest.raises(PermissionError, match="outside project root"):
        await tool_file_read(
            {"project_root": str(tmp_path), "path": "../etc/passwd", "max_chars": 100}
        )


@pytest.mark.asyncio
async def test_file_list_path_traversal_denied(tmp_path):
    with pytest.raises(PermissionError, match="outside project root"):
        await tool_file_list({"project_root": str(tmp_path), "path": "../"})


@pytest.mark.asyncio
async def test_file_write_requires_overwrite_flag(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("old", encoding="utf-8")

    with pytest.raises(PermissionError, match="overwrite"):
        await tool_file_write(
            {
                "project_root": str(tmp_path),
                "path": "notes.txt",
                "content": "new",
                "overwrite": False,
            }
        )


@pytest.mark.asyncio
async def test_file_write_new_file_and_list(tmp_path):
    write_out = await tool_file_write(
        {
            "project_root": str(tmp_path),
            "path": "dir/a.txt",
            "content": "abc",
            "overwrite": False,
        }
    )
    write_payload = json.loads(write_out)
    assert write_payload["path"] == "dir/a.txt"
    assert write_payload["bytes_written"] == 3
    assert write_payload["overwrote"] is False

    list_out = await tool_file_list({"project_root": str(tmp_path), "path": "dir"})
    list_payload = json.loads(list_out)
    assert list_payload["path"] == "dir"
    assert {entry["name"] for entry in list_payload["entries"]} == {"a.txt"}
