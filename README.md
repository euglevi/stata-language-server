# Stata-Language-Server

> Write your Stata scripts more fluently!

This is a fork of the original VSCode LSP for Stata. I rigged it a little bit to adapt it to the new version of pygls, to neovim rather than VSCode and I added a formatter. I also changed the logic of some of the codestyle checking.

To install the LSP, just clone the repository and install it with pip or pipx (recommended):

```
git clone https://github.com/euglevi/stata-language-server
cd stata-language-server
pipx install .
``` 

To setup the LSP, you can use the instructions in the neovim manuals: https://neovim.io/doc/user/lsp.html.

I add here my personal config in ~/.config/nvim/lsp/stata-language-server.lua:

```
return {
	cmd = { "stata-language-server" }, -- Path to the server executable
	filetypes = { "stata" }, -- Filetypes to associate with the server
	root_markers = { ".git" },
	single_file_support = true,
	settings = {
		stata = {
			setMaxLineLength = 82, -- Example: Set max line length
			setIndentSpace = 4, -- Example: Set indentation spaces
			enableCompletion = true, -- Enable autocompletion
			enableDocstring = true, -- Enable hover documentation
			enableStyleChecking = true, -- Enable style checking
                        enableFormatting = true, -- Enable formatting
		},
	},
	capabilities = {
		workspace = {
			didChangeConfiguration = {
				dynamicRegistration = true,
			},
		},
	},
}
```



## Description

An extension for [Stata](https://www.stata.com/) on Neovim. It provides codestyle checking, goto-definition, syntax tips, formatting and auto completion.

Developed based on [language server](https://microsoft.github.io/language-server-protocol/), depending on Third-party Python library [pygls](https://github.com/openlawlibrary/pygls).

> Note: Another plugin is recommanded for syntax highlight since Stata Language Server doesn't provide this feature.

## Supported Features

- Codestyle Checking

    When editing a stata do-file, the extension will check documents and show bad codestyle using wavy underlines.

    ![diagnostic](assets/img/diagnostics.gif)

- Syntax tips while hovering

    When hovering on a complete command, a markdown formatted Syntax Description will appear.

    > Note: Not available for 1.abbr. commands(eg: `g`, `gen`); 2.docstring included in another command's docstring(eg: `replace` belongs to `generate`)

    ![hover](assets/img/hover.gif)

    > Note: Docstring files of this extension are only for academic purpose. The original work copyright belongs to StataCorp LLC. See ThirdPartyNotices.txt for details.

- Goto Definition(`generate varname =`)

    Find and jump to the last `generate` place when right-click a variable name and click `Go to Definition`. Can match pattern like `g(enerate)`.

    ![gotoDefinition](assets/img/gotoDefinition.gif)

- Syntax auto completion

    Auto-Completion for most stata commands. Only support complete syntax(eg: `generate`, not `g(enerate)`).

    ![completion](assets/img/completion.gif)

- Formatting

   The LSP incorporates a script for formatting Stata do files based on the suggested codestyle. So far it has worked me well, but there could be bugs.

## Requirements

- Python >= 3.6

## Settings

| Setting Name | Description | Default Value |
|---|---|---|
| `stataServer.setMaxLineLength` | Max line length for codestyle checking | `120` |
| `stataServer.setIndentSpace` | Indent spaces for codetyle checking | `4` |
| `stataServer.enableCompletion` | Turn on/off auto-completion | `true` |
| `stataServer.enableDocstring` | Turn on/off docstring tips | `true` |
| `stataServer.enableStyleChecking` | Turn on/off codestyle checking | `true` |
| `stataServer.enableFormatting` | Turn on/off formatting | `true` |

## Release Notes

Refer to [CHANGELOG.md](https://github.com/HankBO/stata-language-server/blob/main/CHANGELOG.md)

## Issues

Submit [issues](https://github.com/HankBO/stata-language-server/issues) if you find any bug or have any suggestion.
