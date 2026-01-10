"""
File system MCP server implementation for local file access.

Provides secure file operations through Model Context Protocol.
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List
from mcp.server import Server, Tool
from mcp.server.stdio import stdio_server
from mcp.types import TextContent
import logging

logger = logging.getLogger(__name__)


class FileSystemServer(Server):
    """File system MCP server with secure operations."""
    
    def __init__(self, base_path: str = "."):
        """Initialize file system server with base path."""
        self.base_path = Path(base_path).resolve()
    
    async def list_tools(self) -> List[Tool]:
        """List available filesystem tools."""
        return [
            Tool(
                name="read_file",
                description="Read contents of a file from the local filesystem",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to read"
                        }
                    },
                    "required": ["path"]
                }
            ),
            Tool(
                name="write_file",
                description="Write content to a file in the local filesystem",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to the file to write"
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file"
                        }
                    },
                    "required": ["path", "content"]
                }
            ),
            Tool(
                name="list_directory",
                description="List files and directories in a given path",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to list (defaults to current directory)",
                            "default": "."
                        }
                    },
                    "recursive": {
                        "type": "boolean",
                            "description": "Whether to list recursively",
                            "default": False
                        }
                    }
                }
            )
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a filesystem tool with security validation."""
        logger.info(f"Executing filesystem tool: {name} with args: {arguments}")
        
        if name == "read_file":
            return await self._read_file(arguments)
        elif name == "write_file":
            return await self._write_file(arguments)
        elif name == "list_directory":
            return await self._list_directory(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")
    
    async def _read_file(self, args: Dict[str, Any]) -> str:
        """Read file contents with security validation."""
        file_path = args.get("path", "")
        
        # Security: Validate path
        full_path = self._validate_path(file_path)
        if full_path is None:
            raise ValueError("Invalid file path")
        
        try:
            # Security: Check file exists and size
            if not full_path.exists():
                raise FileNotFoundError(f"File not found: {file_path}")
            
            file_size = full_path.stat().st_size
            max_size = 10 * 1024 * 1024  # 10MB limit
            if file_size > max_size:
                raise ValueError(f"File too large: {file_size} (max: {max_size})")
            
            # Security: Check file type
            if full_path.suffix.lower() in ['.exe', '.bat', '.cmd', '.sh', '.ps1']:
                raise ValueError(f"Executable files not allowed: {file_path}")
            
            content = full_path.read_text(encoding='utf-8')
            logger.info(f"Successfully read file: {full_path} ({len(content)} chars)")
            return content
            
        except PermissionError:
            raise PermissionError(f"Permission denied: {file_path}")
        except UnicodeDecodeError:
            raise ValueError(f"File encoding error: {file_path}")
    
    async def _write_file(self, args: Dict[str, Any]) -> str:
        """Write content to file with security validation."""
        file_path = args.get("path", "")
        content = args.get("content", "")
        
        # Security: Validate path
        full_path = self._validate_path(file_path)
        if full_path is None:
            raise ValueError("Invalid file path")
        
        # Security: Check directory exists
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Security: Validate content size
        if len(content) > 1024 * 1024:  # 1MB limit
            raise ValueError(f"Content too large: {len(content)} bytes (max: 1MB)")
        
        try:
            full_path.write_text(content, encoding='utf-8')
            logger.info(f"Successfully wrote file: {full_path} ({len(content)} chars)")
            return f"File written successfully: {full_path}"
            
        except PermissionError:
            raise PermissionError(f"Permission denied: {file_path}")
    
    async def _list_directory(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List directory contents with security validation."""
        path = args.get("path", ".")
        recursive = args.get("recursive", False)
        
        # Security: Validate path
        full_path = self._validate_path(path)
        if full_path is None:
            raise ValueError("Invalid directory path")
        
        if not full_path.is_dir():
            raise ValueError(f"Not a directory: {path}")
        
        try:
            items = []
            if recursive:
                for item in full_path.rglob("*"):
                    if item.is_file():
                        items.append({
                            "name": item.name,
                            "type": "file",
                            "size": item.stat().st_size
                        })
                    elif item.is_dir():
                        items.append({
                            "name": item.name + "/",
                            "type": "directory",
                            "size": 0
                        })
            else:
                for item in full_path.iterdir():
                    item_path = full_path / item
                    if item_path.is_file():
                        items.append({
                            "name": item,
                            "type": "file",
                            "size": item_path.stat().st_size
                        })
                    elif item_path.is_dir():
                        items.append({
                            "name": item + "/",
                            "type": "directory",
                            "size": 0
                        })
            
            logger.info(f"Listed directory: {full_path} ({len(items)} items)")
            return {
                "path": str(full_path),
                "items": items,
                "recursive": recursive
            }
            
        except PermissionError:
            raise PermissionError(f"Permission denied: {path}")
    
    def _validate_path(self, file_path: str) -> Path:
        """Validate and resolve file path with security checks."""
        try:
            path = Path(file_path)
            
            # Security: Resolve path to prevent directory traversal
            resolved = path.resolve()
            
            # Security: Ensure path is within allowed base directory
            try:
                resolved.relative_to(self.base_path)
            except ValueError:
                raise ValueError(f"Path outside allowed directory: {file_path}")
            
            # Security: Check for suspicious patterns
            if ".." in str(resolved) or str(resolved).startswith("/"):
                raise ValueError(f"Invalid path pattern: {file_path}")
            
            return resolved
            
        except Exception as e:
            logger.error(f"Path validation error: {e}")
            return None


async def main():
    """Start the filesystem MCP server."""
    import sys
    
    # Get base path from command line or use current directory
    base_path = sys.argv[1] if len(sys.argv) > 1 else "."
    
    server = FileSystemServer(base_path=base_path)
    
    async with stdio_server(server) as streams:
        logger.info(f"Filesystem MCP server started on: {base_path}")
        await server.run(
            *streams,
            # Read-only access by default
            read_only=base_path != "."  # Only allow writes in current directory
        )