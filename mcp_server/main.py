#!/usr/bin/env python3
"""
Main Lightroom MCP Server
Composes all module servers into a unified interface
"""
import logging
import os
import sys
from typing import Dict, Any
from fastmcp import FastMCP
from mcp_server.shared.resilient_client import resilient_client_manager
from mcp_server.middleware import error_handler

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Create main server
main_server = FastMCP("Lightroom Classic Bridge")

# Import all server modules
from mcp_server.servers.system import system_server
from mcp_server.servers.catalog import catalog_server
from mcp_server.servers.develop import develop_server  # Now imports from modular package
from mcp_server.servers.preview import preview_server

from mcp_server.servers.compact import compact_server, register_legacy_servers

# Which tools to expose: "compact" (default, ~20 broad tools), "legacy" (the original
# one-tool-per-slider set) or "all". The compact tools wrap the legacy implementations.
TOOLSET = os.environ.get("LIGHTROOM_MCP_TOOLS", "compact").lower()
LEGACY_SERVERS = [system_server.server, catalog_server.server, develop_server.server, preview_server.server]
register_legacy_servers(*LEGACY_SERVERS)

if TOOLSET in ("compact", "all"):
    main_server.mount(compact_server)
if TOOLSET in ("legacy", "all"):
    for legacy_server in LEGACY_SERVERS:
        main_server.mount(legacy_server)

# Note: FastMCP doesn't have startup/shutdown decorators in current API
# Connection management is handled by the client_manager when tools are called
async def initialize_connection():
    """Initialize Lightroom connection"""
    logger.info("Starting Lightroom Classic Bridge MCP Server")
    await resilient_client_manager.connect()

# Guide tools describing the legacy tool set: only exposed with it
legacy_only_tool = main_server.tool if TOOLSET in ("legacy", "all") else (lambda fn: fn)

# Add server-level tool for listing capabilities
@legacy_only_tool
async def list_capabilities() -> Dict[str, Any]:
    """
    List all available tool categories and capabilities.

    Returns:
        Server capabilities and tool organization
    """
    return {
        "server": "Lightroom Classic Bridge",
        "version": "2.0.0",
        "modules": {
            "system": {
                "description": "Connection and system management",
                "tool_count": 4,
                "prefix": "system_"
            },
            "catalog": {
                "description": "Photo catalog operations",
                "tool_count": 11,
                "prefix": "catalog_",
                "status": "Active"
            },
            "develop": {
                "description": "Photo development and editing",
                "tool_count": 118,
                "prefix": "develop_",
                "status": "Active"
            },
            "preview": {
                "description": "Preview generation",
                "tool_count": 4,
                "prefix": "preview_",
                "status": "Active"
            }
        },
        "features": {
            "batch_operations": True,
            "error_handling": True,
            "auto_reconnect": True,
            "parameter_validation": True
        }
    }

# Set up error handling - FastMCP doesn't support exception_handler decorator in current version
# error_handler.setup_error_handlers(main_server)

@legacy_only_tool
async def get_quick_start_guide() -> Dict[str, Any]:
    """
    Get a quick start guide for AI photo editing.

    Returns:
        Step-by-step guide for common workflows
    """
    return {
        "welcome": "Lightroom Classic MCP Bridge",
        "version": "2.0.0",
        "quick_start_workflow": [
            {
                "step": 1,
                "action": "Check photo selection",
                "tool": "catalog_get_selected_photos",
                "why": "Ensure you have a photo to edit"
            },
            {
                "step": 2,
                "action": "Generate initial preview",
                "tool": "preview_generate_current",
                "why": "See the starting point"
            },
            {
                "step": 3,
                "action": "Get current settings",
                "tool": "develop_get_current_settings",
                "why": "Understand current adjustments"
            },
            {
                "step": 4,
                "action": "Apply auto tone",
                "tool": "develop_auto_tone",
                "why": "Good starting point for adjustments"
            },
            {
                "step": 5,
                "action": "Fine-tune exposure",
                "tool": "develop_adjust_exposure",
                "why": "Adjust overall brightness"
            },
            {
                "step": 6,
                "action": "Generate new preview",
                "tool": "preview_generate_current",
                "why": "See the results of your edits"
            }
        ],
        "tips": [
            "Always check if a photo is selected before editing",
            "Use preview_generate_current frequently to see changes",
            "develop_set_parameters is efficient for multiple adjustments",
            "develop_reset_all undoes all changes",
            "Use develop_apply_style for quick professional looks"
        ]
    }

if __name__ == "__main__":
    # Run in STDIO mode
    main_server.run(transport="stdio")