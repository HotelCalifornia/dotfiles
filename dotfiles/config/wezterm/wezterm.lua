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

return apply_mixins({
    color_scheme = 'OneDark (Gogh)',
    initial_cols = 120,
    initial_rows = 36,
    font = wezterm.font('Fira Mono for Powerline'),
    font_size = 14.0,
    background = {
        [1] = {
            source = {
                Color = 'rgb(179, 220, 219)',
            },
            height = '100%',
            width = '100%',
            hsb = {
                brightness = 0.05012822697759764,
            },
        },
        [2] = {
            source = {
                File = '/Users/hotel/Developer/Pokemon-Terminal/pokemonterminal/Images/Generation IV - Sinnoh/471.jpg',
            },
            hsb = {
                brightness = 0.05012822697759764,
            },
            height = 'Contain',
            repeat_y = 'NoRepeat',
            vertical_align = 'Middle',
        },
    },
})
