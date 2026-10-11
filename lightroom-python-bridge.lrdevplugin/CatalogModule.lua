-- CatalogModule.lua
-- Catalog operations API wrapper for Phase 4
-- Enhanced with lightweight error handling

-- Lazy imports to avoid loading issues
local LrApplication = nil
local LrTasks = import 'LrTasks'
local LrProgressScope = nil

-- Get ErrorUtils from global state (created in PluginInit.lua)
local function getErrorUtils()
    if _G.LightroomPythonBridge and _G.LightroomPythonBridge.ErrorUtils then
        return _G.LightroomPythonBridge.ErrorUtils
    end
    -- Minimal fallback if global not available
    return {
        safeCall = function(func, ...) return LrTasks.pcall(func, ...) end,
        createError = function(code, message) return { error = { code = code or "ERROR", message = message or "An error occurred", severity = "error" } } end,
        createSuccess = function(result) return { result = result or {} } end,
        wrapCallback = function(callback) return callback end,
        validateRequired = function() return true end,
        CODES = { MISSING_PARAM = "MISSING_PARAM", CATALOG_ACCESS_FAILED = "CATALOG_ACCESS_FAILED" }
    }
end

local ErrorUtils = getErrorUtils()

-- Lazy load Lightroom modules
local function ensureLrModules()
    if not LrApplication then
        LrApplication = import 'LrApplication'
    end
    if not LrProgressScope then
        LrProgressScope = import 'LrProgressScope'
    end
end

-- Get logger from global state (defensive)
local function getLogger()
    if _G.LightroomPythonBridge and _G.LightroomPythonBridge.logger then
        return _G.LightroomPythonBridge.logger
    end
    local LrLogger = import 'LrLogger'
    local logger = LrLogger('CatalogModule')
    logger:enable("logfile")
    return logger
end

local CatalogModule = {}

-- Search photos with flexible criteria
function CatalogModule.searchPhotos(params, callback)
    local wrappedCallback = ErrorUtils.wrapCallback(callback, "searchPhotos")
    
    -- Ensure modules are loaded
    local moduleSuccess, moduleError = ErrorUtils.safeCall(ensureLrModules)
    if not moduleSuccess then
        wrappedCallback(ErrorUtils.createError(ErrorUtils.CODES.RESOURCE_UNAVAILABLE, 
            "Failed to load Lightroom modules: " .. tostring(moduleError)))
        return
    end
    
    local logger = getLogger()
    local criteria = (params and params.criteria) or {}
    local limit = (params and params.limit) or 100
    local offset = (params and params.offset) or 0
    
    -- Validate limit parameter
    if limit < 1 or limit > 10000 then
        wrappedCallback(ErrorUtils.createError(ErrorUtils.CODES.INVALID_PARAM_VALUE, 
            "Limit must be between 1 and 10000"))
        return
    end
    
    -- Validate offset parameter
    if offset < 0 then
        wrappedCallback(ErrorUtils.createError(ErrorUtils.CODES.INVALID_PARAM_VALUE, 
            "Offset must be 0 or greater"))
        return
    end
    
    logger:debug("Searching photos with criteria")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        -- Get photos using the most appropriate method
        local allPhotos
        local photosSuccess, photosResult = ErrorUtils.safeCall(function()
            return catalog:getTargetPhotos()
        end)
        
        if photosSuccess and photosResult and #photosResult > 0 then
            allPhotos = photosResult
        else
            -- Fallback to all photos
            local allSuccess, allResult = ErrorUtils.safeCall(function()
                return catalog:getAllPhotos()
            end)
            
            if allSuccess then
                allPhotos = allResult
            else
                wrappedCallback(ErrorUtils.createError(ErrorUtils.CODES.CATALOG_ACCESS_FAILED, 
                    "Failed to access catalog photos"))
                return
            end
        end
        
        if not allPhotos or #allPhotos == 0 then
            wrappedCallback(ErrorUtils.createSuccess({
                photos = {},
                total = 0,
                offset = offset,
                limit = limit,
                hasMore = false
            }, "No photos found in catalog"))
            return
        end
        
        local results = {}
        local total = #allPhotos
        local startIndex = offset + 1
        local endIndex = math.min(offset + limit, total)
        
        for i = startIndex, endIndex do
            local photo = allPhotos[i]
            
            local photoData = {
                id = photo.localIdentifier,
                keywords = {},
                collections = {}
            }
            
            -- Safely get photo metadata
            ErrorUtils.safeCall(function()
                photoData.filename = photo:getFormattedMetadata("fileName")
                photoData.folderPath = photo:getFormattedMetadata("folderName")
                photoData.path = photo:getRawMetadata("path")
                photoData.captureTime = photo:getFormattedMetadata("dateTimeOriginal")
                photoData.rating = photo:getRawMetadata("rating")
                photoData.fileFormat = photo:getRawMetadata("fileFormat")
                photoData.isVirtualCopy = photo:getRawMetadata("isVirtualCopy")
            end)
            
            -- Get keywords
            ErrorUtils.safeCall(function()
                local keywords = photo:getRawMetadata("keywords")
                if keywords then
                    for _, keyword in ipairs(keywords) do
                        local success, name = ErrorUtils.safeCall(function()
                            return keyword:getName()
                        end)
                        if success and name then
                            table.insert(photoData.keywords, name)
                        end
                    end
                end
            end)
            
            -- Get collections
            ErrorUtils.safeCall(function()
                local collections = photo:getContainedCollections()
                if collections then
                    for _, collection in ipairs(collections) do
                        local success, name = ErrorUtils.safeCall(function()
                            return collection:getName()
                        end)
                        if success and name then
                            table.insert(photoData.collections, name)
                        end
                    end
                end
            end)
            
            table.insert(results, photoData)
        end
        
        logger:info("Found " .. total .. " photos, returning " .. #results)
        
        wrappedCallback(ErrorUtils.createSuccess({
            photos = results,
            total = total,
            offset = offset,
            limit = limit,
            hasMore = endIndex < total
        }, "Photos retrieved successfully"))
    end)
end

-- Get photo metadata
function CatalogModule.getPhotoMetadata(params, callback)
    ensureLrModules()
    local logger = getLogger()
    
    local photoId = nil
    
    -- Safe parameter extraction with error handling
    local success, result = ErrorUtils.safeCall(function()
        logger:debug("getPhotoMetadata called with params: " .. tostring(params))
        
        if params then
            logger:debug("params is a table with type: " .. type(params))
            local count = 0
            for k, v in pairs(params) do
                logger:debug("  param[" .. tostring(k) .. "] = " .. tostring(v) .. " (type: " .. type(v) .. ")")
                count = count + 1
            end
            logger:debug("Total params count: " .. count)
            
            photoId = params.photoId
        else
            logger:error("params is nil!")
        end
        
        logger:debug("Extracted photoId: " .. tostring(photoId))
        return photoId
    end)
    
    if not success then
        logger:error("Error in parameter extraction: " .. tostring(result))
    else
        photoId = result
    end
    
    if not photoId then
        callback({
            error = {
                code = "MISSING_PHOTO_ID",
                message = "Photo ID is required"
            }
        })
        return
    end
    
    logger:debug("Getting metadata for photo: " .. photoId)
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        -- Find photo by localIdentifier
        local photo = catalog:getPhotoByLocalId(tonumber(photoId))
        
        if not photo then
            callback({
                error = {
                    code = "PHOTO_NOT_FOUND",
                    message = "Photo with ID " .. photoId .. " not found"
                }
            })
            return
        end
        
        -- Collect comprehensive metadata
        local rawRating = photo:getRawMetadata("rating")
        logger:debug("Raw rating value: " .. tostring(rawRating) .. " (type: " .. type(rawRating) .. ")")
        
        local metadata = {
            -- Basic info
            id = photo.localIdentifier,
            filename = photo:getFormattedMetadata("fileName"),
            folderPath = photo:getFormattedMetadata("folderName"),
            filepath = photo:getRawMetadata("path"),
            fileSize = photo:getFormattedMetadata("fileSize"),
            fileFormat = photo:getRawMetadata("fileFormat"),
            
            -- Capture info
            captureTime = photo:getFormattedMetadata("dateTimeOriginal"),
            cameraMake = photo:getFormattedMetadata("cameraMake"),
            cameraModel = photo:getFormattedMetadata("cameraModel"),
            lens = photo:getFormattedMetadata("lens"),
            
            -- Settings
            iso = photo:getFormattedMetadata("isoSpeedRating"),
            aperture = photo:getFormattedMetadata("aperture"),
            shutterSpeed = photo:getFormattedMetadata("shutterSpeed"),
            focalLength = photo:getFormattedMetadata("focalLength"),
            
            -- Lightroom specific
            rating = rawRating or 0,  -- Default to 0 if nil
            colorLabel = photo:getRawMetadata("colorNameForLabel"),
            isVirtualCopy = photo:getRawMetadata("isVirtualCopy"),
            stackPosition = photo:getRawMetadata("stackPositionInFolder"),
            
            -- Develop status (use basic metadata only)
            -- hasAdjustments/hasCrop not available in all Lightroom versions
            
            -- Keywords and collections
            keywords = {},
            collections = {}
        }
        
        logger:debug("Metadata table rating: " .. tostring(metadata.rating))
        
        -- Get keywords
        local keywords = photo:getRawMetadata("keywords")
        if keywords then
            for _, keyword in ipairs(keywords) do
                table.insert(metadata.keywords, {
                    name = keyword:getName(),
                    synonyms = keyword:getSynonyms()
                })
            end
        end
        
        -- Get collections
        local collections = photo:getContainedCollections()
        if collections then
            for _, collection in ipairs(collections) do
                table.insert(metadata.collections, {
                    name = collection:getName(),
                    type = collection:type()
                })
            end
        end
        
        logger:info("Retrieved metadata for photo: " .. metadata.filename)
        logger:debug("About to send metadata with rating: " .. tostring(metadata.rating))
        
        callback({
            result = metadata
        })
    end)
end

-- Get current selection
function CatalogModule.getSelectedPhotos(params, callback)
    local wrappedCallback = ErrorUtils.wrapCallback(callback, "getSelectedPhotos")
    
    -- Ensure modules are loaded
    local moduleSuccess, moduleError = ErrorUtils.safeCall(ensureLrModules)
    if not moduleSuccess then
        wrappedCallback(ErrorUtils.createError(ErrorUtils.CODES.RESOURCE_UNAVAILABLE, 
            "Failed to load Lightroom modules: " .. tostring(moduleError)))
        return
    end
    
    local logger = getLogger()
    logger:debug("Getting currently selected photos")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local selectedSuccess, selectedPhotos = ErrorUtils.safeCall(function()
            return catalog:getTargetPhotos()
        end)
        
        if not selectedSuccess or not selectedPhotos or #selectedPhotos == 0 then
            wrappedCallback(ErrorUtils.createSuccess({
                photos = {},
                count = 0
            }, "No photos currently selected"))
            return
        end
        
        local results = {}
        
        for i, photo in ipairs(selectedPhotos) do
            local photoData = {
                id = photo.localIdentifier
            }
            
            -- Safely get photo metadata
            ErrorUtils.safeCall(function()
                photoData.filename = photo:getFormattedMetadata("fileName")
                photoData.folderPath = photo:getFormattedMetadata("folderName")
                photoData.path = photo:getRawMetadata("path")
                photoData.captureTime = photo:getFormattedMetadata("dateTimeOriginal")
                photoData.rating = photo:getRawMetadata("rating")
                photoData.fileFormat = photo:getRawMetadata("fileFormat")
                photoData.isVirtualCopy = photo:getRawMetadata("isVirtualCopy")
            end)
            
            table.insert(results, photoData)
        end
        
        logger:info("Retrieved " .. #results .. " selected photos")
        
        wrappedCallback(ErrorUtils.createSuccess({
            photos = results,
            count = #results
        }, "Selected photos retrieved successfully"))
    end)
end

-- Set photo selection
function CatalogModule.setSelectedPhotos(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local photoIds = params.photoIds
    
    if not photoIds or type(photoIds) ~= "table" then
        callback({
            error = {
                code = "INVALID_PHOTO_IDS",
                message = "Photo IDs array is required"
            }
        })
        return
    end
    
    logger:debug("Setting photo selection to " .. #photoIds .. " photos")
    
    local catalog = LrApplication.activeCatalog()
    
    -- Use withWriteAccessDo with timeout to prevent blocking
    local writeSuccess, writeError = ErrorUtils.safeCall(function()
        catalog:withWriteAccessDo("Set Photo Selection", function()
            local photos = {}
            local notFound = {}
            
            -- Find all photos by localIdentifier
            for _, photoId in ipairs(photoIds) do
                local photo = catalog:getPhotoByLocalId(tonumber(photoId))
                if photo then
                    table.insert(photos, photo)
                else
                    table.insert(notFound, photoId)
                end
            end
            
            if #photos == 0 then
                error("No photos found with provided IDs")
            end
            
            -- Set selection
            catalog:setSelectedPhotos(photos[1], photos)
            
            -- Return results for success callback
            return {
                selected = #photos,
                notFound = #notFound > 0 and notFound or nil
            }
        end, { timeout = 10 })  -- 10 second timeout
    end)
    
    if writeSuccess then
        logger:info("Successfully set selection to " .. writeError.selected .. " photos")  -- writeError contains results when successful
        callback({
            result = writeError  -- writeError is actually the success result
        })
    else
        logger:error("Failed to set photo selection (write access): " .. tostring(writeError))
        callback({
            error = {
                code = "WRITE_ACCESS_BLOCKED",
                message = "Failed to set photo selection (write access blocked): " .. tostring(writeError)
            }
        })
    end
end

-- Get all photos in catalog
function CatalogModule.getAllPhotos(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local limit = params.limit or 1000  -- Default limit to prevent memory issues
    local offset = params.offset or 0
    
    logger:debug("Getting all photos from catalog")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local allPhotos = catalog:getAllPhotos()
        
        if not allPhotos then
            callback({
                error = {
                    code = "NO_PHOTOS",
                    message = "No photos found in catalog"
                }
            })
            return
        end
        
        logger:info("Found " .. #allPhotos .. " total photos in catalog")
        
        -- Apply pagination
        local startIndex = offset + 1
        local endIndex = math.min(startIndex + limit - 1, #allPhotos)
        local pagedPhotos = {}
        
        for i = startIndex, endIndex do
            local photo = allPhotos[i]
            table.insert(pagedPhotos, {
                id = photo.localIdentifier,
                filename = photo:getFormattedMetadata("fileName"),
                path = photo:getRawMetadata("path"),
                captureTime = photo:getFormattedMetadata("dateTimeOriginal"),
                fileFormat = photo:getRawMetadata("fileFormat"),
                rating = photo:getRawMetadata("rating")
            })
        end
        
        callback({
            result = {
                photos = pagedPhotos,
                total = #allPhotos,
                offset = offset,
                limit = limit,
                returned = #pagedPhotos
            }
        })
    end)
end

-- Find photo by file path
function CatalogModule.findPhotoByPath(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local path = params.path
    
    if not path then
        callback({
            error = {
                code = "MISSING_PATH",
                message = "File path is required"
            }
        })
        return
    end
    
    logger:debug("Finding photo by path: " .. path)
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local photo = catalog:findPhotoByPath(path)
        
        if not photo then
            callback({
                error = {
                    code = "PHOTO_NOT_FOUND",
                    message = "No photo found at path: " .. path
                }
            })
            return
        end
        
        callback({
            result = {
                id = photo.localIdentifier,
                filename = photo:getFormattedMetadata("fileName"),
                path = photo:getRawMetadata("path"),
                captureTime = photo:getFormattedMetadata("dateTimeOriginal"),
                fileFormat = photo:getRawMetadata("fileFormat"),
                rating = photo:getRawMetadata("rating"),
                camera = photo:getFormattedMetadata("cameraModel")
            }
        })
    end)
end

-- Advanced photo search with criteria
function CatalogModule.findPhotos(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local searchDesc = params.searchDesc or {}
    local limit = params.limit or 100
    
    logger:debug("Finding photos with search criteria")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        -- Simple fallback: just use getAllPhotos with limit
        local allPhotos = catalog:getAllPhotos()
        
        if not allPhotos or #allPhotos == 0 then
            callback({
                result = {
                    photos = {},
                    total = 0,
                    returned = 0
                }
            })
            return
        end
        
        logger:info("Found " .. #allPhotos .. " photos total, applying limit")
        
        -- Apply limit and convert to response format
        local resultPhotos = {}
        local maxResults = math.min(limit, #allPhotos)
        
        for i = 1, maxResults do
            local photo = allPhotos[i]
            table.insert(resultPhotos, {
                id = photo.localIdentifier,
                filename = photo:getFormattedMetadata("fileName"),
                path = photo:getRawMetadata("path"),
                captureTime = photo:getFormattedMetadata("dateTimeOriginal"),
                fileFormat = photo:getRawMetadata("fileFormat"),
                rating = photo:getRawMetadata("rating")
            })
        end
        
        callback({
            result = {
                photos = resultPhotos,
                total = #allPhotos,
                returned = #resultPhotos
            }
        })
    end)
end

-- Parse "YYYY-MM-DD" into a Lightroom time (seconds since 2001-01-01, local time)
local function parseDate(s, endOfDay)
    if type(s) ~= "string" then return nil end
    local y, m, d = s:match("^(%d%d%d%d)-(%d%d?)-(%d%d?)$")
    if not y then return nil end
    local LrDate = import 'LrDate'
    if endOfDay then
        return LrDate.timeFromComponents(tonumber(y), tonumber(m), tonumber(d), 23, 59, 59.999, "local")
    end
    return LrDate.timeFromComponents(tonumber(y), tonumber(m), tonumber(d), 0, 0, 0, "local")
end

local function containsCI(haystack, needle)
    if not needle or needle == "" then return true end
    if not haystack then return false end
    return string.find(string.lower(tostring(haystack)), string.lower(needle), 1, true) ~= nil
end

-- Lightroom reports "grey" (or nothing) for photos without a color label
local function labelName(label)
    if label == nil or label == "" or label == "grey" or label == "gray" then return "none" end
    return label
end

local FLAG_VALUES ={ pick = 1, picked = 1, reject = -1, rejected = -1, unflagged = 0, none = 0 }

-- Catalog-wide, read-only photo query. All filters are optional and combined with AND:
--   dateFrom / dateTo ("YYYY-MM-DD", capture date, inclusive), folder (path substring),
--   filename, camera, lens, keyword (substrings, case-insensitive), minRating / maxRating (0-5),
--   flag ("pick" | "reject" | "unflagged"), colorLabel ("red", "yellow", ..., "none"),
--   fileFormat ("RAW", "JPG", ...), includeVirtualCopies (default true),
--   sort ("captureTime" | "-captureTime"), limit (default 50, max 1000), offset.
function CatalogModule.queryPhotos(params, callback)
    ensureLrModules()
    local logger = getLogger()
    params = params or {}

    local limit = tonumber(params.limit) or 50
    local offset = tonumber(params.offset) or 0
    if limit < 1 or limit > 1000 or offset < 0 then
        callback(ErrorUtils.createError(ErrorUtils.CODES.INVALID_PARAM_VALUE or "INVALID_PARAM_VALUE",
            "limit must be 1-1000 and offset >= 0"))
        return
    end

    local dateFrom, dateTo
    if params.dateFrom then
        dateFrom = parseDate(params.dateFrom, false)
        if not dateFrom then
            callback(ErrorUtils.createError("INVALID_PARAM_VALUE", "dateFrom must be YYYY-MM-DD"))
            return
        end
    end
    if params.dateTo then
        dateTo = parseDate(params.dateTo, true)
        if not dateTo then
            callback(ErrorUtils.createError("INVALID_PARAM_VALUE", "dateTo must be YYYY-MM-DD"))
            return
        end
    end

    local flagValue
    if params.flag then
        flagValue = FLAG_VALUES[string.lower(tostring(params.flag))]
        if flagValue == nil then
            callback(ErrorUtils.createError("INVALID_PARAM_VALUE", "flag must be pick, reject or unflagged"))
            return
        end
    end

    local minRating = tonumber(params.minRating)
    local maxRating = tonumber(params.maxRating)
    local colorLabel = params.colorLabel and string.lower(tostring(params.colorLabel)) or nil
    local includeVirtual = params.includeVirtualCopies ~= false
    -- The message decoder does not unescape strings, so compare paths with "/" separators only
    local function normalizePath(p)
        if not p then return nil end
        return (tostring(p):gsub("\\+", "/"))
    end
    local folderNeedle = params.folder and normalizePath(params.folder) or nil

    local catalog = LrApplication.activeCatalog()
    local success, err = LrTasks.pcall(function()
        catalog:withReadAccessDo(function()
            local allPhotos = catalog:getAllPhotos()
            local raw = catalog:batchGetRawMetadata(allPhotos,
                { "path", "rating", "pickStatus", "colorNameForLabel", "dateTimeOriginal", "fileFormat", "isVirtualCopy" })
            local needFormatted = params.camera or params.lens or params.keyword or params.filename
            local fmt = needFormatted and catalog:batchGetFormattedMetadata(allPhotos,
                { "fileName", "cameraModel", "lens", "keywordTags" }) or {}

            local matches = {}
            for _, photo in ipairs(allPhotos) do
                local r = raw[photo] or {}
                local f = fmt[photo] or {}
                local rating = r.rating or 0
                local label = labelName(r.colorNameForLabel)
                local ok = true
                if ok and not includeVirtual and r.isVirtualCopy then ok = false end
                if ok and dateFrom and (not r.dateTimeOriginal or r.dateTimeOriginal < dateFrom) then ok = false end
                if ok and dateTo and (not r.dateTimeOriginal or r.dateTimeOriginal > dateTo) then ok = false end
                if ok and minRating and rating < minRating then ok = false end
                if ok and maxRating and rating > maxRating then ok = false end
                if ok and flagValue ~= nil and (r.pickStatus or 0) ~= flagValue then ok = false end
                if ok and colorLabel and string.lower(label) ~= colorLabel then ok = false end
                if ok and params.fileFormat and string.upper(tostring(r.fileFormat or "")) ~= string.upper(params.fileFormat) then ok = false end
                if ok and folderNeedle and not containsCI(normalizePath(r.path), folderNeedle) then ok = false end
                if ok and not containsCI(f.fileName, params.filename) then ok = false end
                if ok and not containsCI(f.cameraModel, params.camera) then ok = false end
                if ok and not containsCI(f.lens, params.lens) then ok = false end
                if ok and not containsCI(f.keywordTags, params.keyword) then ok = false end
                if ok then
                    table.insert(matches, { photo = photo, raw = r, time = r.dateTimeOriginal or 0 })
                end
            end

            local descending = params.sort == "-captureTime"
            table.sort(matches, function(a, b)
                if descending then return a.time > b.time end
                return a.time < b.time
            end)

            local page = {}
            local lastIndex = math.min(offset + limit, #matches)
            local pagePhotos = {}
            for i = offset + 1, lastIndex do
                table.insert(pagePhotos, matches[i].photo)
            end
            local pageFmt = (#pagePhotos > 0) and catalog:batchGetFormattedMetadata(pagePhotos,
                { "fileName", "folderName", "dateTimeOriginal", "cameraModel", "lens" }) or {}

            for i = offset + 1, lastIndex do
                local m = matches[i]
                local f = pageFmt[m.photo] or {}
                table.insert(page, {
                    id = m.photo.localIdentifier,
                    filename = f.fileName,
                    folder = f.folderName,
                    path = m.raw.path,
                    captureTime = f.dateTimeOriginal,
                    rating = m.raw.rating or 0,
                    flag = (m.raw.pickStatus == 1 and "pick") or (m.raw.pickStatus == -1 and "reject") or "unflagged",
                    colorLabel = labelName(m.raw.colorNameForLabel),
                    camera = f.cameraModel,
                    lens = f.lens,
                    fileFormat = m.raw.fileFormat,
                    isVirtualCopy = m.raw.isVirtualCopy and true or false,
                })
            end

            logger:info("queryPhotos: " .. #matches .. " matches of " .. #allPhotos .. ", returning " .. #page)
            callback({
                result = {
                    photos = page,
                    total = #matches,
                    catalogTotal = #allPhotos,
                    offset = offset,
                    limit = limit,
                    hasMore = lastIndex < #matches,
                }
            })
        end)
    end)
    if not success then
        logger:error("queryPhotos failed: " .. tostring(err))
        callback(ErrorUtils.createError("CATALOG_ACCESS_FAILED", "queryPhotos failed: " .. tostring(err)))
    end
end

-- Get collections in catalog
function CatalogModule.getCollections(params, callback)
    ensureLrModules()
    local logger = getLogger()
    
    logger:debug("Getting collections from catalog")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local collections = catalog:getChildCollections()
        
        local resultCollections = {}
        for _, collection in ipairs(collections) do
            table.insert(resultCollections, {
                id = collection.localIdentifier,
                name = collection:getName(),
                type = collection:type(),
                photoCount = #collection:getPhotos()
            })
        end
        
        callback({
            result = {
                collections = resultCollections,
                count = #resultCollections
            }
        })
    end)
end

-- Get keywords in catalog
function CatalogModule.getKeywords(params, callback)
    ensureLrModules()
    local logger = getLogger()
    
    logger:debug("Getting keywords from catalog")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local keywords = catalog:getKeywords()
        
        local resultKeywords = {}
        for _, keyword in ipairs(keywords) do
            table.insert(resultKeywords, {
                id = keyword.localIdentifier,
                name = keyword:getName(),
                photoCount = #keyword:getPhotos()
            })
        end
        
        callback({
            result = {
                keywords = resultKeywords,
                count = #resultKeywords
            }
        })
    end)
end

-- Get folders in catalog
function CatalogModule.getFolders(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local includeSubfolders = params.includeSubfolders or false
    
    logger:debug("Getting folders from catalog")
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local rootFolders = catalog:getFolders()
        
        local function buildFolderTree(folder, depth)
            depth = depth or 0
            local folderPath = folder:getPath()
            local folderData = {
                id = folderPath, -- Use path as ID since folders don't have localIdentifier
                name = folder:getName(),
                path = folderPath,
                type = folder:type(),
                depth = depth,
                photoCount = #folder:getPhotos(false), -- Photos directly in this folder
                totalPhotoCount = #folder:getPhotos(true), -- Photos including subfolders
                subfolders = {}
            }
            
            -- Get parent folder info if available
            local parent = folder:getParent()
            if parent then
                folderData.parentId = parent:getPath()
                folderData.parentName = parent:getName()
            end
            
            -- Recursively get subfolders if requested
            if includeSubfolders then
                local children = folder:getChildren()
                if children then
                    for _, child in ipairs(children) do
                        table.insert(folderData.subfolders, buildFolderTree(child, depth + 1))
                    end
                end
            end
            
            return folderData
        end
        
        local resultFolders = {}
        for _, folder in ipairs(rootFolders) do
            table.insert(resultFolders, buildFolderTree(folder))
        end
        
        logger:info("Retrieved " .. #resultFolders .. " root folders from catalog")
        
        callback({
            result = {
                folders = resultFolders,
                count = #resultFolders,
                includeSubfolders = includeSubfolders
            }
        })
    end)
end

-- Batch get formatted metadata for multiple photos
function CatalogModule.batchGetFormattedMetadata(params, callback)
    ensureLrModules()
    local logger = getLogger()
    local photoIds = params.photoIds
    local keys = params.keys or {"fileName", "dateTimeOriginal", "rating"}
    
    logger:debug("Batch metadata - photoIds type: " .. type(photoIds))
    if photoIds then
        logger:debug("Batch metadata - photoIds length: " .. tostring(#photoIds))
        if type(photoIds) == "table" then
            for i, id in ipairs(photoIds) do
                logger:debug("  photoId[" .. i .. "] = " .. tostring(id) .. " (type: " .. type(id) .. ")")
            end
        end
    end
    
    if not photoIds then
        callback({
            error = {
                code = "MISSING_PHOTO_IDS", 
                message = "Photo IDs parameter is missing"
            }
        })
        return
    end
    
    if type(photoIds) ~= "table" then
        callback({
            error = {
                code = "INVALID_PHOTO_IDS_TYPE",
                message = "Photo IDs must be an array, got: " .. type(photoIds)
            }
        })
        return
    end
    
    if #photoIds == 0 then
        callback({
            error = {
                code = "EMPTY_PHOTO_IDS",
                message = "Photo IDs array is empty"
            }
        })
        return
    end
    
    logger:debug("Batch getting metadata for " .. #photoIds .. " photos")
    logger:debug("Keys type: " .. type(keys))
    if type(keys) == "table" then
        logger:debug("Keys length: " .. #keys)
        for i, key in ipairs(keys) do
            logger:debug("  key[" .. i .. "] = " .. tostring(key))
        end
    else
        logger:debug("Keys value: " .. tostring(keys))
    end
    
    local catalog = LrApplication.activeCatalog()
    
    catalog:withReadAccessDo(function()
        local photos = {}
        for _, photoId in ipairs(photoIds) do
            local photo = catalog:getPhotoByLocalId(tonumber(photoId))
            if photo then
                table.insert(photos, photo)
            end
        end
        
        if #photos == 0 then
            callback({
                result = {
                    metadata = {},
                    requested = #photoIds,
                    found = 0
                }
            })
            return
        end
        
        -- Use batch API for efficiency
        local batchResults = catalog:batchGetFormattedMetadata(photos, keys)
        
        local results = {}
        for i, photo in ipairs(photos) do
            local metadata = batchResults[i] or {}
            metadata.id = photo.localIdentifier
            table.insert(results, metadata)
        end
        
        callback({
            result = {
                metadata = results,
                requested = #photoIds,
                found = #photos,
                keys = keys
            }
        })
    end)
end

return CatalogModule