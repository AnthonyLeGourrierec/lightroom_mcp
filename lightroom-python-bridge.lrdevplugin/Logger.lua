-- Logger.lua
local LrLogger = import 'LrLogger'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'

local Logger = {}

-- Initialize logger with plugin-specific configuration
function Logger:init(pluginName)
    self.logger = LrLogger(pluginName)
    self.logger:enable("logfile")
    -- Config:init() runs before this in PluginInit.lua
    local Config = require 'Config'
    self.logLevel = (Config.prefs and Config:get('bridgeLogLevel')) or 'info'
end

local LEVELS = { debug = 1, info = 2, warn = 3, error = 4 }

-- Log level methods
function Logger:debug(message)
    if self.logger and self:shouldLog('debug') then
        self.logger:debug(self:formatMessage(message))
    end
end

function Logger:info(message)
    if self.logger and self:shouldLog('info') then
        self.logger:info(self:formatMessage(message))
    end
end

function Logger:warn(message)
    if self.logger and self:shouldLog('warn') then
        self.logger:warn(self:formatMessage(message))
    end
end

function Logger:error(message)
    if self.logger and self:shouldLog('error') then
        self.logger:error(self:formatMessage(message))
    end
end

-- Helper methods
function Logger:shouldLog(level)
    return (LEVELS[level] or 2) >= (LEVELS[self.logLevel] or 2)
end

function Logger:formatMessage(message)
    return string.format("[%s] %s", os.date("%Y-%m-%d %H:%M:%S"), tostring(message))
end

return Logger