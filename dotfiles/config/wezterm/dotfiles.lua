-- Shared WezTerm config, deployed by dotdrop (d_wezterm). Don't edit the
-- deployed copy: machine-local settings (including the background that
-- `pokemon` writes) belong in ~/.config/wezterm/wezterm.lua, which calls this
-- module with its overrides. Precedence: base < mixins/*.lua < local overrides.
local wezterm = require('wezterm')

local function apply_mixins(config)
    local mixins_dir = wezterm.config_dir .. '/mixins'
    local mixin_files = wezterm.glob(mixins_dir .. '/*.lua')
    for _, path in ipairs(mixin_files) do
        local ok, mixin = pcall(dofile, path)
        if ok and mixin then
            if type(mixin) == 'function' then
                mixin(config)
            elseif type(mixin) == 'table' then
                for k, v in pairs(mixin) do
                    config[k] = v
                end
            end
        elseif not ok then
            wezterm.log_error('Failed to load mixin ' .. path .. ': ' .. tostring(mixin))
        end
    end
    return config
end

return function(overrides)
    local config = apply_mixins({
        color_scheme = 'OneDark (Gogh)',
        initial_cols = 120,
        initial_rows = 36,
        font = wezterm.font('Fira Mono for Powerline'),
        font_size = 14.0,
    })
    for k, v in pairs(overrides or {}) do
        config[k] = v
    end
    return config
end
