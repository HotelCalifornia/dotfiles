set number
set showmatch
set ignorecase
set mouse=v
set hlsearch
set tabstop=4
set softtabstop=4
set expandtab
set shiftwidth=4
set autoindent
set cc=80,120

filetype plugin indent on

syntax on
set mouse=a
set clipboard=unnamedplus

filetype plugin on

set cursorline
set ttyfast

call plug#begin()
    Plug 'navarasu/onedark.nvim'
    Plug 'nvim-lualine/lualine.nvim'
    Plug 'kyazdani42/nvim-web-devicons'
    Plug 'neoclide/coc.nvim', {'branch': 'release'}
    Plug 'kyazdani42/nvim-tree.lua'
call plug#end()

" return to last position on file open
au BufReadPost * if line("'\"") > 0 && line("'\"") <= line("$")
    \ | exe "normal! g'\"" | endif

"** lua plugin configuration **"

lua << END
require('onedark').setup {
    style = 'warmer',
    transparent = true,
}
require('onedark').load()

require('lualine').setup {
    options = { theme = 'onedark' },
}

require('nvim-tree').setup {
    open_on_setup = true,
    open_on_tab = true,
    update_focused_file = {
        enable = true,
    },
    auto_close = true,
}
END
