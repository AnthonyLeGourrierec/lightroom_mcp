"""
Main develop server - coordinates all develop tool modules
"""
from typing import Dict, Any
from mcp_server.shared.base import LightroomServerModule

# Import all develop tool modules
from .basic_tools import setup_basic_tools
from .parameter_management import setup_parameter_management_tools
from .tone_curves import setup_tone_curve_tools, setup_advanced_tone_curve_tools
from .color_tools import setup_hsl_tools, setup_color_grading_tools
from .detail_tools import setup_detail_tools
from .effects_tools import setup_effects_tools
from .lens_tools import setup_lens_corrections_tools
from .calibration_tools import setup_calibration_tools
from .helper_tools import setup_helper_tools
from .masking_tools import setup_masking_tools
from .geometry_tools import setup_geometry_tools

class DevelopServer(LightroomServerModule):
    """Photo development and editing tools - modular architecture"""
    
    @property
    def name(self) -> str:
        return "Lightroom Develop Tools"
    
    @property
    def prefix(self) -> str:
        return "develop"
    
    def _setup_tools(self):
        """Register all develop tools from focused modules"""
        # Basic adjustments (15 tools)
        setup_basic_tools(self.server, self.execute_command)
        
        # Parameter management (8 tools) 
        setup_parameter_management_tools(self.server, self.execute_command)
        
        # Tone curves (12 tools total)
        setup_tone_curve_tools(self.server, self.execute_command)
        setup_advanced_tone_curve_tools(self.server, self.execute_command)
        
        # Color adjustments (34 tools total)
        setup_hsl_tools(self.server, self.execute_command)
        setup_color_grading_tools(self.server, self.execute_command)
        
        # Detail & sharpening (8 tools)
        setup_detail_tools(self.server, self.execute_command)
        
        # Effects & vignetting (8 tools)
        setup_effects_tools(self.server, self.execute_command)
        
        # Lens corrections (14 tools)
        setup_lens_corrections_tools(self.server, self.execute_command)
        
        # Camera calibration (7 tools)
        setup_calibration_tools(self.server, self.execute_command)
        
        # High-level helpers (2 tools)
        setup_helper_tools(self.server, self.execute_command)

        # Masking: AI masks, linear/radial gradients, Enhance
        setup_masking_tools(self.server, self.execute_command)
        
        # Crop, transform, curves per channel, color grading, snapshots, presets
        setup_geometry_tools(self.server, self.execute_command)

# Create server instance
develop_server = DevelopServer()