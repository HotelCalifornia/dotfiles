vim.opt.number = true
vim.opt.showmatch = true
vim.opt.ignorecase = true
vim.opt.hlsearch = true
vim.opt.expandtab = true
vim.opt.autoindent = true
vim.opt.cursorline = true
vim.opt.ttyfast = true
vim.opt.cc = { 80, 120 }
vim.opt.tabstop = 4
vim.opt.softtabstop = 4
vim.opt.shiftwidth = 4
vim.opt.mouse = 'a'
vim.opt.clipboard = 'unnamedplus'

local Plug = vim.fn['plug#']
vim.call('plug#begin')

Plug 'navarasu/onedark.nvim'
Plug 'nvim-lualine/lualine.nvim'
Plug 'kyazdani42/nvim-web-devicons'
Plug('neoclide/coc.nvim', { branch = 'release' })
Plug 'kyazdani42/nvim-tree.lua'

vim.call('plug#end')

vim.g.loaded_netrw = 1
vim.g.loaded_netrwPlugin = 1

require('onedark').setup {
    style = 'warmer',
    transparent = true,
}
require('onedark').load()

require('lualine').setup {
    options = { theme = 'onedark' },
}

require('nvim-web-devicons').setup()

require('nvim-tree').setup {
    open_on_tab = true,
    update_focused_file = {
        enable = true,
    },
    hijack_directories = {
        enable = false,
        auto_open = false,
    },
}
--[[
-- environment setup
-- open NvimTree by default
--  - if a directory was opened, cd to it and focus the tree
--  - otherwise, direct NvimTree to find the file in the tree and not to steal focus
-- open a terminal split below the main file
--]]
vim.api.nvim_create_autocmd({ 'VimEnter' }, {
    callback = function(data)
        local opts = { focus = false }
        if vim.fn.isdirectory(data.file) == 1 then
            vim.cmd.cd(data.file)
            opts.focus = true
        elseif vim.fn.filereadable(data.file) == 1 or (data.file == '' and vim.bo[data.buf].buftype == '') then
            opts.find_file = true
        end

        require('nvim-tree.api').tree.toggle(opts)

        local current_buf = vim.api.nvim_get_current_buf()

        local buf = vim.api.nvim_create_buf(false, false)
        local win = vim.api.nvim_open_win(buf, false, {
            split = 'below',
            height = 10,
        })
        vim.api.nvim_win_call(win, function() return vim.cmd 'terminal' end)
    end
})

-- close neovim if NvimTree is the last open buffer
vim.api.nvim_create_autocmd("BufEnter", {
    nested = true,
    callback = function()
        local function match_buf(buf, name)
            return vim.api.nvim_buf_get_name(buf):match(name) ~= nil
        end
        if
            (#vim.api.nvim_list_wins() == 2
                and (match_buf(2, 'NvimTree_') and match_buf(0, 'term://')))
            or (#vim.api.nvim_list_wins() == 1 and match_buf(0, "NvimTree_"))
        then
            vim.cmd 'quit'
        end
    end
})

-- return to last position on file open
vim.api.nvim_create_autocmd('BufReadPost', {
    callback = function()
        if vim.fn.line("'\"") > 0 and vim.fn.line("'\"") <= vim.fn.line('$') then
            vim.cmd("normal! g'\"")
        end
    end
})

vim.api.nvim_set_keymap('i', '<cr>', '', {
    expr = true,
    noremap = true,
    replace_keycodes = true,
    callback = function() return vim.fn['coc#pum#visible']() == 1 and vim.fn['coc#pum#confirm']() or '<cr>' end,
})

