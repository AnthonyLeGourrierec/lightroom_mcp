"""
Preview server module for image generation
Priority implementation for AI visual feedback loop
"""
from typing import Dict, Any, Optional, List
from mcp_server.shared.base import LightroomServerModule
from mcp_server.shared.resilient_client import resilient_client_manager
import base64
import logging
import os
from pathlib import Path
import time
from PIL import Image
import io
import numpy as np

logger = logging.getLogger(__name__)

class PreviewServer(LightroomServerModule):
    """Preview generation tools for visual feedback"""

    @property
    def name(self) -> str:
        return "Lightroom Preview Tools"

    @property
    def prefix(self) -> str:
        return "preview"

    async def _handle_chunked_preview(self, preview_id: str, chunk_size: int) -> str:
        """Handle chunked preview download and return base64 data"""
        chunks = []
        chunk_index = 0

        while True:
            chunk_result = await self.execute_command("getPreviewChunk", {
                "previewId": preview_id,
                "chunkIndex": chunk_index,
                "chunkSize": chunk_size
            })

            chunks.append(chunk_result.get("chunk", ""))

            if chunk_result.get("isLastChunk", False):
                logger.info(f"Downloaded {chunk_index + 1} chunks")
                break

            chunk_index += 1

        # Combine all chunks
        return "".join(chunks)

    def _generate_preview_filename(self, photo_id: str, size: str, filename_hint: Optional[str] = None, save_path: Optional[str] = None) -> Path:
        """Generate a unique filename for preview storage

        Args:
            photo_id: Photo ID
            size: Preview size
            filename_hint: Optional filename hint
            save_path: Optional directory path or full file path. If None, uses current directory.
                      If it's a directory, generates filename. If it's a file path, uses it directly.
        """
        # Generate base filename
        if filename_hint:
            # Clean the filename hint and use it as the primary name
            clean_hint = "".join(c for c in filename_hint if c.isalnum() or c in "._-")
            # Don't duplicate size if it's already in the hint
            if size.lower() in clean_hint.lower():
                base_name = f"{clean_hint}.jpg"
            else:
                base_name = f"{clean_hint}_{size}.jpg"
        else:
            timestamp = int(time.time() * 1000)
            base_name = f"lr_preview_{photo_id}_{size}_{timestamp}.jpg"

        if save_path:
            path = Path(save_path)

            # Check if it's a directory or file path
            if path.suffix in ['.jpg', '.jpeg']:
                # It's a full file path, use it directly
                # Create parent directory if needed
                path.parent.mkdir(parents=True, exist_ok=True)
                return path
            else:
                # It's a directory path
                path.mkdir(parents=True, exist_ok=True)
                return path / base_name
        else:
            # Default to current working directory
            return Path.cwd() / base_name

    def _resize_and_optimize_jpeg(self, jpeg_data: bytes, size: str, quality: int) -> tuple[bytes, int, int]:
        """Resize and optimize JPEG data based on size parameter

        Returns: (optimized_jpeg_data, actual_width, actual_height)
        """
        # Target sizes for longest edge
        size_targets = {
            "small": 640,
            "medium": 1080,
            "large": 1440,
            "full": None  # No resize for full
        }

        target_size = size_targets.get(size)
        if target_size is None:
            # For full size, just recompress with the specified quality
            img = Image.open(io.BytesIO(jpeg_data))
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=quality, optimize=True)
            return output.getvalue(), img.width, img.height

        # Open image and get dimensions
        img = Image.open(io.BytesIO(jpeg_data))
        orig_width, orig_height = img.size

        # Calculate new dimensions maintaining aspect ratio
        if orig_width > orig_height:
            # Landscape
            new_width = target_size
            new_height = int(target_size * orig_height / orig_width)
        else:
            # Portrait or square
            new_height = target_size
            new_width = int(target_size * orig_width / orig_height)

        # Only resize if the image is larger than target
        if orig_width > new_width or orig_height > new_height:
            # Use LANCZOS resampling for best quality
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        else:
            new_width, new_height = orig_width, orig_height

        # Save with specified quality and optimization
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=quality, optimize=True)

        return output.getvalue(), new_width, new_height

    def _analyze_histogram_from_base64(self, base64_data: str, channels: str = "all") -> Dict[str, Any]:
        """Analyze histogram from base64 image data
        
        Args:
            base64_data: Base64 encoded JPEG data
            channels: "all", "rgb", or "luminance"
        
        Returns:
            Dictionary with histogram data and statistics
        """
        try:
            # Decode base64 to binary and open with PIL
            jpeg_data = base64.b64decode(base64_data)
            img = Image.open(io.BytesIO(jpeg_data))
            
            # Convert to RGB if not already
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Convert to numpy array
            img_array = np.array(img)
            height, width, channels_count = img_array.shape
            
            result = {
                "success": True,
                "image_dimensions": f"{width}x{height}",
                "total_pixels": width * height
            }
            
            if channels in ["all", "rgb"]:
                # RGB channel histograms
                red_channel = img_array[:, :, 0].flatten()
                green_channel = img_array[:, :, 1].flatten()
                blue_channel = img_array[:, :, 2].flatten()
                
                # Calculate histograms (256 bins for 0-255 range)
                red_hist, _ = np.histogram(red_channel, bins=256, range=(0, 256))
                green_hist, _ = np.histogram(green_channel, bins=256, range=(0, 256))
                blue_hist, _ = np.histogram(blue_channel, bins=256, range=(0, 256))
                
                # RGB statistics
                result["rgb"] = {
                    "histograms": {
                        "red": red_hist.tolist(),
                        "green": green_hist.tolist(),
                        "blue": blue_hist.tolist()
                    },
                    "statistics": {
                        "red": {
                            "mean": float(np.mean(red_channel)),
                            "median": float(np.median(red_channel)),
                            "std": float(np.std(red_channel)),
                            "min": int(np.min(red_channel)),
                            "max": int(np.max(red_channel))
                        },
                        "green": {
                            "mean": float(np.mean(green_channel)),
                            "median": float(np.median(green_channel)),
                            "std": float(np.std(green_channel)),
                            "min": int(np.min(green_channel)),
                            "max": int(np.max(green_channel))
                        },
                        "blue": {
                            "mean": float(np.mean(blue_channel)),
                            "median": float(np.median(blue_channel)),
                            "std": float(np.std(blue_channel)),
                            "min": int(np.min(blue_channel)),
                            "max": int(np.max(blue_channel))
                        }
                    }
                }
                
                # Clipping analysis for RGB
                total_pixels = width * height
                result["rgb"]["clipping"] = {
                    "shadows_clipped": {
                        "red": int(np.sum(red_channel == 0)),
                        "green": int(np.sum(green_channel == 0)),
                        "blue": int(np.sum(blue_channel == 0))
                    },
                    "highlights_clipped": {
                        "red": int(np.sum(red_channel == 255)),
                        "green": int(np.sum(green_channel == 255)),
                        "blue": int(np.sum(blue_channel == 255))
                    },
                    "shadow_clipping_percent": {
                        "red": float(np.sum(red_channel == 0) / total_pixels * 100),
                        "green": float(np.sum(green_channel == 0) / total_pixels * 100),
                        "blue": float(np.sum(blue_channel == 0) / total_pixels * 100)
                    },
                    "highlight_clipping_percent": {
                        "red": float(np.sum(red_channel == 255) / total_pixels * 100),
                        "green": float(np.sum(green_channel == 255) / total_pixels * 100),
                        "blue": float(np.sum(blue_channel == 255) / total_pixels * 100)
                    }
                }
            
            if channels in ["all", "luminance"]:
                # Luminance histogram (weighted average of RGB)
                # Standard luminance weights: 0.299*R + 0.587*G + 0.114*B
                luminance = (0.299 * img_array[:, :, 0] + 
                           0.587 * img_array[:, :, 1] + 
                           0.114 * img_array[:, :, 2]).flatten().astype(np.uint8)
                
                luminance_hist, _ = np.histogram(luminance, bins=256, range=(0, 256))
                
                result["luminance"] = {
                    "histogram": luminance_hist.tolist(),
                    "statistics": {
                        "mean": float(np.mean(luminance)),
                        "median": float(np.median(luminance)),
                        "std": float(np.std(luminance)),
                        "min": int(np.min(luminance)),
                        "max": int(np.max(luminance))
                    },
                    "clipping": {
                        "shadows_clipped": int(np.sum(luminance == 0)),
                        "highlights_clipped": int(np.sum(luminance == 255)),
                        "shadow_clipping_percent": float(np.sum(luminance == 0) / len(luminance) * 100),
                        "highlight_clipping_percent": float(np.sum(luminance == 255) / len(luminance) * 100)
                    },
                    "tonal_distribution": {
                        "shadows_percent": float(np.sum(luminance < 85) / len(luminance) * 100),  # 0-84
                        "midtones_percent": float(np.sum((luminance >= 85) & (luminance < 170)) / len(luminance) * 100),  # 85-169
                        "highlights_percent": float(np.sum(luminance >= 170) / len(luminance) * 100)  # 170-255
                    }
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Histogram analysis failed: {e}")
            return {
                "success": False,
                "error": f"Failed to analyze histogram: {str(e)}"
            }

    def _save_preview_to_disk(self, base64_data: str, file_path: Path, size: str = "full", quality: int = 90) -> Dict[str, Any]:
        """Save base64 preview data to disk with optional resizing and optimization"""
        try:
            # Decode base64 to binary
            jpeg_data = base64.b64decode(base64_data)

            # Resize and optimize if not full size
            if size != "full":
                jpeg_data, actual_width, actual_height = self._resize_and_optimize_jpeg(jpeg_data, size, quality)
            else:
                # For full size, get dimensions without resizing
                img = Image.open(io.BytesIO(jpeg_data))
                actual_width, actual_height = img.size

            # Write to file
            with open(file_path, 'wb') as f:
                f.write(jpeg_data)

            # Get file stats
            file_stats = file_path.stat()

            return {
                "success": True,
                "file_path": str(file_path),
                "file_size_bytes": file_stats.st_size,
                "file_size_mb": round(file_stats.st_size / (1024 * 1024), 2),
                "actual_width": actual_width,
                "actual_height": actual_height
            }
        except Exception as e:
            logger.error(f"Failed to save preview to disk: {e}")
            return {
                "success": False,
                "error": f"Failed to save preview: {str(e)}"
            }

    def _setup_tools(self):
        """Register preview tools"""

        @self.server.tool
        async def preview_generate(
            photo_id: Optional[str] = None,
            size: str = "medium",
            quality: Optional[int] = None,
            filename: Optional[str] = None,
            save_path: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Generate a JPEG preview of a photo and save it to disk.

            This is the primary tool for AI agents to visualize photos
            and the effects of their develop adjustments. The preview is
            saved to disk and the file path is returned.

            Args:
                photo_id: Photo ID (uses current selection if not provided)
                size: Preview size (maintains aspect ratio):
                      - "small": 640px longest edge, quality 50
                      - "medium": 1080px longest edge, quality 90
                      - "large": 1440px longest edge, quality 90
                      - "full": original resolution, quality 90
                quality: Optional JPEG quality override (1-100)
                filename: Optional filename hint for the saved file
                save_path: Optional save location. Can be:
                          - None: saves to current working directory (recommended)
                          - Directory path: saves to that directory with auto-generated name
                          - Full file path: saves to exact path (e.g., "./my_preview.jpg")

            Returns:
                Dictionary with file_path and metadata
            """
            # Get photo ID if not provided
            if not photo_id:
                try:
                    selected = await self.execute_command("catalog.getSelectedPhotos", {})
                    if selected.get("count", 0) == 0:
                        return {
                            "success": False,
                            "error": "No photo selected in Lightroom",
                            "hint": "Please select a photo or provide photo_id parameter"
                        }
                    photo_id = str(selected["photos"][0]["id"])
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to get selected photo: {e}"
                    }

            # Set quality defaults based on size if not specified
            if quality is None:
                quality_defaults = {
                    "small": 50,   # Very compressed for tiny files
                    "medium": 90,  # Good balance for 1080p viewing
                    "large": 90,   # Higher quality for larger images
                    "full": 90     # High quality for full resolution
                }
                quality = quality_defaults.get(size, 90)

            # Lightroom size is now handled properly in PreviewModule.lua
            # We just pass through the size parameter
            lightroom_size = size

            params = {
                "photoId": photo_id,
                "size": lightroom_size,
                "quality": quality,
                "base64": True  # Always get base64 so we can save to disk
            }

            try:
                result = await self.execute_command("generatePreview", params)
                logger.debug(f"Generate preview result keys: {list(result.keys())}")

                # Handle chunked transfer
                if result.get("preview") == "CHUNKED_TRANSFER":
                    logger.info("Handling chunked preview transfer")

                    preview_id = result.get("previewId")
                    chunk_size = result.get("chunkSize", 0)
                    info = result.get("info", {})

                    # Download chunks until we get isLastChunk
                    chunks = []
                    chunk_index = 0

                    while True:
                        logger.debug(f"Downloading chunk {chunk_index}...")
                        chunk_result = await self.execute_command("getPreviewChunk", {
                            "previewId": preview_id,
                            "chunkIndex": chunk_index,
                            "chunkSize": chunk_size
                        })

                        chunk_data = chunk_result.get("chunk", "")
                        chunks.append(chunk_data)
                        logger.debug(f"Chunk {chunk_index}: {len(chunk_data)} chars, isLastChunk: {chunk_result.get('isLastChunk', False)}")

                        if chunk_result.get("isLastChunk", False):
                            logger.info(f"Downloaded {chunk_index + 1} chunks, total size: {chunk_result.get('totalSize', 'unknown')} bytes")
                            break

                        chunk_index += 1

                    # Combine all chunks
                    full_data = "".join(chunks)
                    logger.info(f"Combined {len(chunks)} chunks into {len(full_data)} chars")

                    # Generate filename and save to disk
                    file_path = self._generate_preview_filename(photo_id, size, filename, save_path)
                    save_result = self._save_preview_to_disk(full_data, file_path, size, quality)

                    if save_result["success"]:
                        response = {
                            "success": True,
                            "file_path": save_result["file_path"],
                            "photo_id": info.get("photoId", photo_id),
                            "size": size,
                            "actual_width": save_result.get("actual_width", info.get("width")),
                            "actual_height": save_result.get("actual_height", info.get("height")),
                            "original_width": info.get("width"),  # Original photo dimensions
                            "original_height": info.get("height"),
                            "lightroom_requested": f"{info.get('requestedWidth', 'unknown')}x{info.get('requestedHeight', 'unknown')}",
                            "file_size_bytes": save_result["file_size_bytes"],
                            "file_size_mb": save_result["file_size_mb"],
                            "transfer_mode": "chunked",
                            "chunks_downloaded": chunk_index + 1,
                            "quality": quality
                        }
                        logger.info(f"Preview saved to: {save_result['file_path']}")
                        return response
                    else:
                        return save_result

                # Handle direct response (non-chunked)
                else:
                    info = result.get("info", {})
                    preview_data = result.get("preview")

                    if preview_data:
                        # Generate filename and save to disk
                        file_path = self._generate_preview_filename(photo_id, size, filename, save_path)
                        save_result = self._save_preview_to_disk(preview_data, file_path, size, quality)

                        if save_result["success"]:
                            response = {
                                "success": True,
                                "file_path": save_result["file_path"],
                                "photo_id": info.get("photoId", photo_id),
                                "size": size,
                                "actual_width": save_result.get("actual_width", info.get("width")),
                                "actual_height": save_result.get("actual_height", info.get("height")),
                                "original_width": info.get("width"),  # Original photo dimensions
                                "original_height": info.get("height"),
                                "lightroom_requested": f"{info.get('requestedWidth', 'unknown')}x{info.get('requestedHeight', 'unknown')}",
                                "file_size_bytes": save_result["file_size_bytes"],
                                "file_size_mb": save_result["file_size_mb"],
                                "transfer_mode": "direct",
                                "quality": quality
                            }
                            logger.info(f"Preview saved to: {save_result['file_path']}")
                            return response
                        else:
                            return save_result
                    else:
                        return {
                            "success": False,
                            "error": "No preview data returned from Lightroom"
                        }

            except Exception as e:
                logger.error(f"Preview generation failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "hint": "Ensure a photo is selected in Lightroom"
                }

        @self.server.tool
        async def preview_generate_current(
            filename: Optional[str] = None,
            save_path: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Generate a preview of the currently selected photo and save to disk.

            Simplified version for quick iteration during editing.
            Always uses medium size (1080px longest edge) and quality 90 for efficient files.

            Args:
                filename: Optional filename hint for the saved file
                save_path: Optional save location. Can be:
                          - None: saves to current working directory (recommended)
                          - Directory path: saves to that directory with auto-generated name
                          - Full file path: saves to exact path (e.g., "./current_preview.jpg")

            Returns:
                Dictionary with file_path and metadata
            """
            # Get currently selected photo ID
            try:
                selected = await self.execute_command("catalog.getSelectedPhotos", {})
                if selected.get("count", 0) == 0:
                    return {
                        "success": False,
                        "error": "No photo selected in Lightroom"
                    }

                photo_id = str(selected["photos"][0]["id"])

                # Generate preview with photo ID
                # Use "medium" size (1080px) with quality 90 for smaller files
                params = {
                    "photoId": photo_id,
                    "size": "medium",  # 1080px longest edge
                    "quality": 90,
                    "base64": True
                }

                result = await self.execute_command("generatePreview", params)

                # Handle chunked transfer
                if result.get("preview") == "CHUNKED_TRANSFER":
                    preview_id = result.get("previewId")
                    chunk_size = result.get("chunkSize", 0)
                    info = result.get("info", {})

                    # Download chunks until we get isLastChunk
                    chunks = []
                    chunk_index = 0

                    while True:
                        chunk_result = await self.execute_command("getPreviewChunk", {
                            "previewId": preview_id,
                            "chunkIndex": chunk_index,
                            "chunkSize": chunk_size
                        })

                        chunks.append(chunk_result.get("chunk", ""))

                        if chunk_result.get("isLastChunk", False):
                            break

                        chunk_index += 1

                    # Combine all chunks
                    full_data = "".join(chunks)

                    # Generate filename and save to disk
                    file_path = self._generate_preview_filename(photo_id, "medium", filename, save_path)
                    save_result = self._save_preview_to_disk(full_data, file_path, "medium", 90)

                    if save_result["success"]:
                        return {
                            "success": True,
                            "file_path": save_result["file_path"],
                            "photo_id": info.get("photoId", photo_id),
                            "size": "medium",
                            "actual_width": save_result.get("actual_width", info.get("width", info.get("size"))),
                            "actual_height": save_result.get("actual_height", info.get("height", info.get("size"))),
                            "file_size_bytes": save_result["file_size_bytes"],
                            "file_size_mb": save_result["file_size_mb"],
                            "transfer_mode": "chunked",
                            "quality": 90
                        }
                    else:
                        return save_result

                # Handle direct response
                info = result.get("info", {})
                preview_data = result.get("preview")

                if preview_data:
                    # Generate filename and save to disk
                    file_path = self._generate_preview_filename(photo_id, "medium", filename, save_path)
                    save_result = self._save_preview_to_disk(preview_data, file_path, "medium", 90)

                    if save_result["success"]:
                        return {
                            "success": True,
                            "file_path": save_result["file_path"],
                            "photo_id": info.get("photoId", photo_id),
                            "size": "medium",
                            "actual_width": save_result.get("actual_width", info.get("width", info.get("size"))),
                            "actual_height": save_result.get("actual_height", info.get("height", info.get("size"))),
                            "file_size_bytes": save_result["file_size_bytes"],
                            "file_size_mb": save_result["file_size_mb"],
                            "transfer_mode": "direct",
                            "quality": 90
                        }
                    else:
                        return save_result
                else:
                    return {
                        "success": False,
                        "error": "No preview data returned from Lightroom"
                    }

            except Exception as e:
                logger.error(f"Current preview generation failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "hint": "Ensure a photo is selected in Lightroom"
                }

        @self.server.tool
        async def preview_export_jpeg(
            photo_id: str,
            out_dir: str,
            file_name: Optional[str] = None,
            long_edge: int = 2048,
            quality: int = 90
        ) -> Dict[str, Any]:
            """
            Render a photo with its current develop settings to a JPEG file
            through Lightroom's export pipeline.

            Use this (not preview_generate) to see the result of fresh edits:
            Lightroom's cached thumbnails can be stale or blank right after an edit.
            Never overwrites existing files (collisions get a numeric suffix).

            Args:
                photo_id: Photo ID to export
                out_dir: Destination folder (created if missing)
                file_name: File name without extension (default: original name)
                long_edge: Long edge in pixels (default 2048)
                quality: JPEG quality 1-100 (default 90)

            Returns:
                Path of the written JPEG
            """
            params: Dict[str, Any] = {
                "photoId": str(photo_id),
                "outDir": out_dir.replace("\\", "/"),
                "longEdge": long_edge,
                "quality": quality,
            }
            if file_name:
                params["fileName"] = file_name
            result = await self.execute_command("exportJpeg", params)
            return {"success": True, "path": result.get("path"), "long_edge": long_edge}

        @self.server.tool
        async def preview_export_with_crops(
            photo_id: str,
            out_dir: str,
            file_name: str,
            crops: Optional[List[Dict[str, Any]]] = None,
            long_edge: int = 6000,
            view_long_edge: int = 1600
        ) -> Dict[str, Any]:
            """
            Export the current edit at full size, then write a downscaled view copy and
            100% crops of chosen areas, for close inspection of noise, halos and sharpness.

            crops: [{"name": "dome", "left": 0.36, "top": 0.33, "right": 0.66, "bottom": 0.52}, ...]
            (normalized 0..1 of the displayed image). Never overwrites existing files.

            Returns paths of the full export, the view copy and each crop, plus simple
            tonal statistics (luminance percentiles, clipping) of the full image.
            """
            params: Dict[str, Any] = {"photoId": str(photo_id), "outDir": out_dir.replace("\\", "/"),
                                      "fileName": file_name, "longEdge": long_edge, "quality": 95}
            exported = await self.execute_command("exportJpeg", params)
            full_path = Path(exported["path"])
            image = Image.open(full_path).convert("RGB")

            def unique(path: Path) -> Path:
                candidate, n = path, 2
                while candidate.exists():
                    candidate = path.with_name(f"{path.stem}-{n}{path.suffix}")
                    n += 1
                return candidate

            view = image.copy()
            view.thumbnail((view_long_edge, view_long_edge))
            view_path = unique(full_path.with_name(f"{full_path.stem}_view.jpg"))
            view.save(view_path, quality=90)

            crop_paths = {}
            width, height = image.size
            for crop in crops or []:
                box = (int(crop["left"] * width), int(crop["top"] * height),
                       int(crop["right"] * width), int(crop["bottom"] * height))
                crop_path = unique(full_path.with_name(f"{full_path.stem}_crop_{crop.get('name', len(crop_paths))}.jpg"))
                image.crop(box).save(crop_path, quality=95)
                crop_paths[crop.get("name", str(len(crop_paths)))] = str(crop_path)

            pixels = np.asarray(image, dtype=np.float32)
            luminance = 0.2126 * pixels[..., 0] + 0.7152 * pixels[..., 1] + 0.0722 * pixels[..., 2]
            stats = {
                "luminance_percentiles": {str(p): round(float(np.percentile(luminance, p)), 1) for p in (1, 5, 50, 95, 99)},
                "clipped_shadows_pct": round(float((luminance <= 2).mean() * 100), 2),
                "clipped_highlights_pct": round(float((pixels.max(axis=-1) >= 254).mean() * 100), 2),
                "mean_rgb": [round(float(v), 1) for v in pixels.reshape(-1, 3).mean(axis=0)],
            }
            return {"success": True, "full": str(full_path), "view": str(view_path),
                    "crops": crop_paths, "stats": stats}

        @self.server.tool
        async def preview_compare(
            image_paths: List[str], out_path: str, height: int = 1600, labels: Optional[List[str]] = None
        ) -> Dict[str, Any]:
            """
            Put exported JPEGs side by side (same height) in one comparison image, e.g.
            before / after. Never overwrites: a suffix is added if out_path exists.
            """
            from PIL import ImageDraw
            images = []
            for path in image_paths:
                img = Image.open(path).convert("RGB")
                images.append(img.resize((int(img.width * height / img.height), height)))
            gap = 20
            canvas = Image.new("RGB", (sum(i.width for i in images) + gap * (len(images) - 1), height), "white")
            x = 0
            draw = ImageDraw.Draw(canvas)
            for i, img in enumerate(images):
                canvas.paste(img, (x, 0))
                if labels and i < len(labels):
                    draw.rectangle((x, 0, x + 12 * len(labels[i]) + 20, 36), fill="black")
                    draw.text((x + 10, 10), labels[i], fill="white")
                x += img.width + gap
            target, n = Path(out_path), 2
            while target.exists():
                target = Path(out_path).with_name(f"{Path(out_path).stem}-{n}{Path(out_path).suffix}")
                n += 1
            canvas.save(target, quality=90)
            return {"success": True, "path": str(target)}

        @self.server.tool
        async def preview_get_info(
            photo_id: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Get information about preview generation for a photo.

            Args:
                photo_id: Photo ID (uses current selection if not provided)

            Returns:
                Preview generation information
            """
            # Get photo ID if not provided
            if not photo_id:
                try:
                    selected = await self.execute_command("catalog.getSelectedPhotos", {})
                    if selected.get("count", 0) == 0:
                        return {
                            "success": False,
                            "error": "No photo selected in Lightroom"
                        }
                    photo_id = str(selected["photos"][0]["id"])
                except Exception as e:
                    return {
                        "success": False,
                        "error": f"Failed to get selected photo: {e}"
                    }

            try:
                result = await self.execute_command("getPreviewInfo", {"photoId": photo_id})

                return {
                    "success": True,
                    "photo_id": photo_id,
                    "available_sizes": {
                        "small": "640px longest edge, quality 50",
                        "medium": "1080px longest edge, quality 90",
                        "large": "1440px longest edge, quality 90",
                        "full": "original resolution, quality 90"
                    },
                    "max_quality": 100,
                    "note": "Previews save to current directory by default. Use save_path to override.",
                    "lightroom_info": result
                }

            except Exception as e:
                logger.error(f"Preview info failed: {e}")
                return {
                    "success": True,  # Return basic info even if Lightroom command fails
                    "photo_id": photo_id,
                    "available_sizes": {
                        "small": "640px longest edge, quality 50",
                        "medium": "1080px longest edge, quality 90",
                        "large": "1440px longest edge, quality 90",
                        "full": "original resolution, quality 90"
                    },
                    "max_quality": 100,
                    "note": "Previews save to current directory by default. Use save_path to override.",
                    "lightroom_info": "Default info (Lightroom command unavailable)"
                }

        @self.server.tool
        async def preview_generate_comparison(
            before_settings: Optional[Dict[str, float]] = None,
            after_settings: Optional[Dict[str, float]] = None,
            size: str = "medium",
            quality: Optional[int] = None,
            save_path: Optional[str] = None
        ) -> Dict[str, Any]:
            """
            Generate before/after comparison previews and save them to disk.

            Useful for AI agents to evaluate the impact of adjustments.

            Args:
                before_settings: Develop settings for "before" (None = current)
                after_settings: Develop settings for "after"
                size: Preview size (small, medium, large, full)
                quality: Optional JPEG quality override (1-100)
                save_path: Optional save location directory

            Returns:
                File paths and metadata for both previews
            """
            try:
                selected = await self.execute_command("catalog.getSelectedPhotos", {})
                if selected.get("count", 0) == 0:
                    return {
                        "success": False,
                        "error": "No photo selected"
                    }

                photo_id = str(selected["photos"][0]["id"])

                # Set quality defaults based on size if not specified
                if quality is None:
                    quality_defaults = {
                        "small": 50,
                        "medium": 90,
                        "large": 90,
                        "full": 90
                    }
                    quality = quality_defaults.get(size, 90)

                original_settings = await self.execute_command(
                    "develop.getSettings",
                    {"photoId": photo_id}
                )

                if before_settings:
                    await self.execute_command(
                        "develop.applySettings",
                        {"photoId": photo_id, "settings": before_settings}
                    )

                # Generate before preview
                before_result = await self.execute_command("generatePreview", {
                    "photoId": photo_id,
                    "size": size,
                    "quality": quality,
                    "base64": True
                })

                # Handle chunked transfer for before preview
                if before_result.get("preview") == "CHUNKED_TRANSFER":
                    before_data = await self._handle_chunked_preview(
                        before_result.get("previewId"),
                        before_result.get("chunkSize", 0)
                    )
                    before_info = before_result.get("info", {})
                else:
                    before_data = before_result.get("preview")
                    before_info = before_result.get("info", {})

                # Save before preview to disk
                before_file_path = self._generate_preview_filename(photo_id, size, "before", save_path)
                before_save_result = self._save_preview_to_disk(before_data, before_file_path, size, quality)

                if not before_save_result["success"]:
                    return before_save_result

                if after_settings:
                    await self.execute_command(
                        "develop.applySettings",
                        {"photoId": photo_id, "settings": after_settings}
                    )

                # Generate after preview
                after_result = await self.execute_command("generatePreview", {
                    "photoId": photo_id,
                    "size": size,
                    "quality": quality,
                    "base64": True
                })

                # Handle chunked transfer for after preview
                if after_result.get("preview") == "CHUNKED_TRANSFER":
                    after_data = await self._handle_chunked_preview(
                        after_result.get("previewId"),
                        after_result.get("chunkSize", 0)
                    )
                    after_info = after_result.get("info", {})
                else:
                    after_data = after_result.get("preview")
                    after_info = after_result.get("info", {})

                # Save after preview to disk
                after_file_path = self._generate_preview_filename(photo_id, size, "after", save_path)
                after_save_result = self._save_preview_to_disk(after_data, after_file_path, size, quality)

                if not after_save_result["success"]:
                    return after_save_result

                await self.execute_command(
                    "develop.applySettings",
                    {"photoId": photo_id, "settings": original_settings["settings"]}
                )

                return {
                    "success": True,
                    "photo_id": photo_id,
                    "before": {
                        "file_path": before_save_result["file_path"],
                        "actual_width": before_save_result.get("actual_width", before_info.get("width")),
                        "actual_height": before_save_result.get("actual_height", before_info.get("height")),
                        "file_size_bytes": before_save_result["file_size_bytes"],
                        "file_size_mb": before_save_result["file_size_mb"]
                    },
                    "after": {
                        "file_path": after_save_result["file_path"],
                        "actual_width": after_save_result.get("actual_width", after_info.get("width")),
                        "actual_height": after_save_result.get("actual_height", after_info.get("height")),
                        "file_size_bytes": after_save_result["file_size_bytes"],
                        "file_size_mb": after_save_result["file_size_mb"]
                    },
                    "size": size,
                    "quality": quality
                }

            except Exception as e:
                logger.error(f"Comparison generation failed: {e}")
                return {
                    "success": False,
                    "error": str(e)
                }

        @self.server.tool
        async def preview_generate_batch(
            photo_ids: List[str],
            size: str = "small",
            quality: int = 85
        ) -> Dict[str, Any]:
            """
            Generate previews for multiple photos.

            Efficient batch generation for browsing/selection.

            Args:
                photo_ids: List of photo IDs
                size: Preview size (recommend "small" for batches)
                quality: JPEG quality

            Returns:
                Dictionary of previews by photo ID
            """
            result = await self.execute_command("generateBatchPreviews", {
                "photoIds": photo_ids,
                "size": size,
                "quality": quality
            })

            return {
                "success": True,
                "count": len(result.get("previews", [])),
                "previews": result.get("previews", [])
            }

        @self.server.tool
        async def histogram_analyze_current() -> Dict[str, Any]:
            """
            Analyze RGB and luminance histograms of the currently selected photo.
            
            Generates a small preview (640px) optimized for histogram analysis,
            then calculates histograms, statistics, and clipping analysis for
            RGB channels and luminance.
            
            Returns:
                Dictionary with histogram data, statistics, and analysis
            """
            try:
                # Get currently selected photo
                selected = await self.execute_command("catalog.getSelectedPhotos", {})
                if selected.get("count", 0) == 0:
                    return {
                        "success": False,
                        "error": "No photo selected in Lightroom",
                        "hint": "Please select a photo and try again"
                    }
                
                photo_id = str(selected["photos"][0]["id"])
                
                # Generate small, low-quality preview for histogram analysis
                params = {
                    "photoId": photo_id,
                    "size": "small",  # 640px longest edge
                    "quality": 30,    # Low quality, we only need pixel data
                    "base64": True
                }
                
                result = await self.execute_command("generatePreview", params)
                
                # Handle chunked transfer if needed
                if result.get("preview") == "CHUNKED_TRANSFER":
                    preview_id = result.get("previewId")
                    chunk_size = result.get("chunkSize", 0)
                    info = result.get("info", {})
                    
                    # Download chunks
                    chunks = []
                    chunk_index = 0
                    
                    while True:
                        chunk_result = await self.execute_command("getPreviewChunk", {
                            "previewId": preview_id,
                            "chunkIndex": chunk_index,
                            "chunkSize": chunk_size
                        })
                        
                        chunks.append(chunk_result.get("chunk", ""))
                        
                        if chunk_result.get("isLastChunk", False):
                            break
                        
                        chunk_index += 1
                    
                    full_data = "".join(chunks)
                else:
                    full_data = result.get("preview")
                    info = result.get("info", {})
                
                if not full_data:
                    return {
                        "success": False,
                        "error": "No preview data returned from Lightroom"
                    }
                
                # Analyze histogram from the preview data
                histogram_result = self._analyze_histogram_from_base64(full_data, "all")
                
                if histogram_result.get("success"):
                    # Add metadata
                    histogram_result.update({
                        "photo_id": photo_id,
                        "preview_size": "small (640px longest edge)",
                        "preview_quality": 30,
                        "analysis_type": "RGB + Luminance"
                    })
                
                return histogram_result
                
            except Exception as e:
                logger.error(f"Histogram analysis failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "hint": "Ensure a photo is selected in Lightroom"
                }

        @self.server.tool
        async def histogram_analyze_rgb() -> Dict[str, Any]:
            """
            Analyze RGB channel histograms of the currently selected photo.
            
            Generates a small preview optimized for analysis, then calculates
            histograms, statistics, and clipping analysis for Red, Green,
            and Blue channels only.
            
            Returns:
                Dictionary with RGB histogram data and statistics
            """
            try:
                # Get currently selected photo
                selected = await self.execute_command("catalog.getSelectedPhotos", {})
                if selected.get("count", 0) == 0:
                    return {
                        "success": False,
                        "error": "No photo selected in Lightroom",
                        "hint": "Please select a photo and try again"
                    }
                
                photo_id = str(selected["photos"][0]["id"])
                
                # Generate small, low-quality preview for histogram analysis
                params = {
                    "photoId": photo_id,
                    "size": "small",  # 640px longest edge
                    "quality": 30,    # Low quality, we only need pixel data
                    "base64": True
                }
                
                result = await self.execute_command("generatePreview", params)
                
                # Handle chunked transfer if needed
                if result.get("preview") == "CHUNKED_TRANSFER":
                    preview_id = result.get("previewId")
                    chunk_size = result.get("chunkSize", 0)
                    
                    # Download chunks
                    chunks = []
                    chunk_index = 0
                    
                    while True:
                        chunk_result = await self.execute_command("getPreviewChunk", {
                            "previewId": preview_id,
                            "chunkIndex": chunk_index,
                            "chunkSize": chunk_size
                        })
                        
                        chunks.append(chunk_result.get("chunk", ""))
                        
                        if chunk_result.get("isLastChunk", False):
                            break
                        
                        chunk_index += 1
                    
                    full_data = "".join(chunks)
                else:
                    full_data = result.get("preview")
                
                if not full_data:
                    return {
                        "success": False,
                        "error": "No preview data returned from Lightroom"
                    }
                
                # Analyze RGB histogram only
                histogram_result = self._analyze_histogram_from_base64(full_data, "rgb")
                
                if histogram_result.get("success"):
                    # Add metadata
                    histogram_result.update({
                        "photo_id": photo_id,
                        "preview_size": "small (640px longest edge)",
                        "preview_quality": 30,
                        "analysis_type": "RGB channels only"
                    })
                
                return histogram_result
                
            except Exception as e:
                logger.error(f"RGB histogram analysis failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "hint": "Ensure a photo is selected in Lightroom"
                }

        @self.server.tool
        async def histogram_analyze_luminance() -> Dict[str, Any]:
            """
            Analyze luminance histogram of the currently selected photo.
            
            Generates a small preview optimized for analysis, then calculates
            luminance histogram, statistics, clipping analysis, and tonal
            distribution (shadows/midtones/highlights).
            
            Returns:
                Dictionary with luminance histogram data and tonal analysis
            """
            try:
                # Get currently selected photo
                selected = await self.execute_command("catalog.getSelectedPhotos", {})
                if selected.get("count", 0) == 0:
                    return {
                        "success": False,
                        "error": "No photo selected in Lightroom",
                        "hint": "Please select a photo and try again"
                    }
                
                photo_id = str(selected["photos"][0]["id"])
                
                # Generate small, low-quality preview for histogram analysis
                params = {
                    "photoId": photo_id,
                    "size": "small",  # 640px longest edge
                    "quality": 30,    # Low quality, we only need pixel data
                    "base64": True
                }
                
                result = await self.execute_command("generatePreview", params)
                
                # Handle chunked transfer if needed
                if result.get("preview") == "CHUNKED_TRANSFER":
                    preview_id = result.get("previewId")
                    chunk_size = result.get("chunkSize", 0)
                    
                    # Download chunks
                    chunks = []
                    chunk_index = 0
                    
                    while True:
                        chunk_result = await self.execute_command("getPreviewChunk", {
                            "previewId": preview_id,
                            "chunkIndex": chunk_index,
                            "chunkSize": chunk_size
                        })
                        
                        chunks.append(chunk_result.get("chunk", ""))
                        
                        if chunk_result.get("isLastChunk", False):
                            break
                        
                        chunk_index += 1
                    
                    full_data = "".join(chunks)
                else:
                    full_data = result.get("preview")
                
                if not full_data:
                    return {
                        "success": False,
                        "error": "No preview data returned from Lightroom"
                    }
                
                # Analyze luminance histogram only
                histogram_result = self._analyze_histogram_from_base64(full_data, "luminance")
                
                if histogram_result.get("success"):
                    # Add metadata
                    histogram_result.update({
                        "photo_id": photo_id,
                        "preview_size": "small (640px longest edge)",
                        "preview_quality": 30,
                        "analysis_type": "Luminance only"
                    })
                
                return histogram_result
                
            except Exception as e:
                logger.error(f"Luminance histogram analysis failed: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "hint": "Ensure a photo is selected in Lightroom"
                }

# Create server instance
preview_server = PreviewServer()