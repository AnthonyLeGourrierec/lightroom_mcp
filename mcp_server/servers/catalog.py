"""
Catalog server module for photo management
Essential for photo selection and metadata access
"""
from typing import Dict, Any, Optional, List, Union
from mcp_server.shared.base import LightroomServerModule
import logging

logger = logging.getLogger(__name__)

class CatalogServer(LightroomServerModule):
    """Photo catalog operations"""
    
    @property
    def name(self) -> str:
        return "Lightroom Catalog Tools"
    
    @property
    def prefix(self) -> str:
        return "catalog"
    
    def _setup_tools(self):
        """Register catalog tools"""
        
        @self.server.tool
        async def catalog_get_selected_photos() -> Dict[str, Any]:
            """
            Get currently selected photos in Lightroom.
            
            Essential for AI agents to know which photo(s) they're working on.
            
            Returns:
                Selected photos with metadata
            """
            result = await self.execute_command("getSelectedPhotos")
            
            return {
                "success": True,
                "count": result.get("count", 0),
                "photos": result.get("photos", []),
                "has_selection": result.get("count", 0) > 0
            }
        
        @self.server.tool
        async def catalog_select_photo(
            photo_id: Union[str, int]
        ) -> Dict[str, Any]:
            """
            Select a specific photo in Lightroom.
            
            Allows AI agents to change which photo they're editing.
            
            Args:
                photo_id: Photo ID to select
                
            Returns:
                Selection confirmation
            """
            await self.execute_command("setSelectedPhotos", {
                "photoIds": [str(photo_id)]
            })
            
            return {
                "success": True,
                "selected_photo_id": str(photo_id),
                "message": "Photo selected"
            }
        
        @self.server.tool
        async def catalog_get_all_photos(
            limit: int = 100,
            offset: int = 0
        ) -> Dict[str, Any]:
            """
            Get all photos in the catalog with pagination.
            
            For AI agents to browse available photos.
            
            Args:
                limit: Maximum photos to return (default 100)
                offset: Starting position for pagination
                
            Returns:
                List of photos with metadata
            """
            result = await self.execute_command("getAllPhotos", {
                "limit": limit,
                "offset": offset
            })
            
            return {
                "success": True,
                "total_count": result.get("totalCount", 0),
                "returned_count": len(result.get("photos", [])),
                "photos": result.get("photos", []),
                "limit": limit,
                "offset": offset,
                "has_more": result.get("totalCount", 0) > offset + limit
            }
        
        @self.server.tool
        async def catalog_search_photos(
            criteria: Dict[str, Any],
            limit: int = 100
        ) -> Dict[str, Any]:
            """
            Search photos with flexible criteria.
            
            Powerful search for AI agents to find specific photos.
            
            Args:
                criteria: Search criteria dict with fields like:
                    - rating: {"min": 3, "max": 5}
                    - captureDate: {"after": "2023-01-01"}
                    - keywords: ["landscape", "sunset"]
                    - fileFormat: "RAW"
                limit: Maximum results
                
            Returns:
                Matching photos
            """
            result = await self.execute_command("searchPhotos", {
                "criteria": criteria,
                "limit": limit
            })
            
            return {
                "success": True,
                "count": len(result.get("photos", [])),
                "photos": result.get("photos", []),
                "criteria": criteria
            }

        @self.server.tool
        async def catalog_query_photos(
            date_from: Optional[str] = None,
            date_to: Optional[str] = None,
            folder: Optional[str] = None,
            filename: Optional[str] = None,
            camera: Optional[str] = None,
            lens: Optional[str] = None,
            keyword: Optional[str] = None,
            min_rating: Optional[int] = None,
            max_rating: Optional[int] = None,
            flag: Optional[str] = None,
            color_label: Optional[str] = None,
            file_format: Optional[str] = None,
            include_virtual_copies: bool = True,
            newest_first: bool = False,
            limit: int = 50,
            offset: int = 0
        ) -> Dict[str, Any]:
            """
            Search the WHOLE catalog (not just the current selection). Read-only.

            All filters are optional and combined with AND. Text filters are
            case-insensitive substrings.

            Args:
                date_from: Capture date on or after, "YYYY-MM-DD"
                date_to: Capture date on or before, "YYYY-MM-DD"
                folder: Substring of the file path, e.g. "2026-09-4_apero"
                filename: Substring of the file name, e.g. "IMG_04"
                camera: Substring of the camera model
                lens: Substring of the lens name
                keyword: Substring of the photo's keywords
                min_rating: Minimum star rating (0-5)
                max_rating: Maximum star rating (0-5)
                flag: "pick", "reject" or "unflagged"
                color_label: "red", "yellow", "green", "blue", "purple" or "none"
                file_format: "RAW", "JPG", "DNG", "TIFF", "VIDEO", ...
                include_virtual_copies: Include virtual copies (default True)
                newest_first: Sort by capture time descending (default oldest first)
                limit: Max photos returned, 1-1000 (default 50)
                offset: Pagination offset

            Returns:
                Matching photos (id, filename, path, capture time, rating, flag,
                label, camera, lens) plus total match count
            """
            params: Dict[str, Any] = {
                "dateFrom": date_from,
                "dateTo": date_to,
                "folder": folder,
                "filename": filename,
                "camera": camera,
                "lens": lens,
                "keyword": keyword,
                "minRating": min_rating,
                "maxRating": max_rating,
                "flag": flag,
                "colorLabel": color_label,
                "fileFormat": file_format,
                "includeVirtualCopies": include_virtual_copies,
                "sort": "-captureTime" if newest_first else "captureTime",
                "limit": limit,
                "offset": offset,
            }
            params = {k: v for k, v in params.items() if v is not None}
            result = await self.execute_command("queryPhotos", params)

            return {
                "success": True,
                "total": result.get("total", 0),
                "catalog_total": result.get("catalogTotal", 0),
                "returned": len(result.get("photos", [])),
                "has_more": result.get("hasMore", False),
                "photos": result.get("photos", []),
            }

        @self.server.tool
        async def catalog_get_photo_metadata(
            photo_id: Union[str, int]
        ) -> Dict[str, Any]:
            """
            Get comprehensive metadata for a photo.
            
            Detailed information for AI analysis.
            
            Args:
                photo_id: Photo ID
                
            Returns:
                Complete photo metadata including EXIF data
            """
            result = await self.execute_command("getPhotoMetadata", {
                "photoId": str(photo_id)
            })
            
            return {
                "success": True,
                "photo_id": str(photo_id),
                "metadata": result
            }
        
        @self.server.tool
        async def catalog_get_collections() -> Dict[str, Any]:
            """
            Get all collections in the catalog.
            
            For AI agents to understand photo organization.
            
            Returns:
                List of collections with photo counts
            """
            result = await self.execute_command("getCollections")
            
            return {
                "success": True,
                "count": len(result.get("collections", [])),
                "collections": result.get("collections", [])
            }
        
        @self.server.tool
        async def catalog_get_keywords() -> Dict[str, Any]:
            """
            Get all keywords used in the catalog.
            
            Helps AI agents understand photo categorization.
            
            Returns:
                Keywords with usage counts
            """
            result = await self.execute_command("getKeywords")
            
            return {
                "success": True,
                "count": len(result.get("keywords", [])),
                "keywords": result.get("keywords", [])
            }
        
        @self.server.tool
        async def catalog_get_folders() -> Dict[str, Any]:
            """
            Get all folders in the catalog.
            
            For AI agents to understand folder organization.
            
            Returns:
                Folder hierarchy with photo counts
            """
            result = await self.execute_command("getFolders")
            
            return {
                "success": True,
                "count": len(result.get("folders", [])),
                "folders": result.get("folders", [])
            }
        
        @self.server.tool
        async def catalog_set_rating(
            photo_id: Union[str, int],
            rating: int
        ) -> Dict[str, Any]:
            """
            Set rating for a photo.
            
            Allows AI agents to rate photos based on analysis.
            
            Args:
                photo_id: Photo ID
                rating: Rating (0-5 stars)
                
            Returns:
                Rating confirmation
            """
            if not 0 <= rating <= 5:
                raise ValueError(f"Rating must be 0-5, got {rating}")
            
            await self.execute_command("setPhotoRating", {
                "photoId": str(photo_id),
                "rating": rating
            })
            
            return {
                "success": True,
                "photo_id": str(photo_id),
                "rating": rating,
                "message": f"Photo rated {rating} stars"
            }
        
        @self.server.tool
        async def catalog_add_keywords(
            photo_id: Union[str, int],
            keywords: List[str]
        ) -> Dict[str, Any]:
            """
            Add keywords to a photo.
            
            Allows AI agents to tag photos based on content analysis.
            
            Args:
                photo_id: Photo ID
                keywords: List of keywords to add
                
            Returns:
                Keywords confirmation
            """
            await self.execute_command("addPhotoKeywords", {
                "photoId": str(photo_id),
                "keywords": keywords
            })
            
            return {
                "success": True,
                "photo_id": str(photo_id),
                "keywords_added": keywords,
                "count": len(keywords)
            }
        
        @self.server.tool
        async def catalog_get_photo_info(
            photo_id: Union[str, int]
        ) -> Dict[str, Any]:
            """
            Get basic photo information.
            
            Quick access to essential photo details.
            
            Args:
                photo_id: Photo ID
                
            Returns:
                Basic photo information
            """
            result = await self.execute_command("getPhotoInfo", {
                "photoId": str(photo_id)
            })
            
            return {
                "success": True,
                "photo_id": str(photo_id),
                "info": result
            }

# Create server instance
catalog_server = CatalogServer()