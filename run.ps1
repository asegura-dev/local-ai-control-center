<#
.SYNOPSIS
    uv wrapper that keeps the virtual environment out of this folder.

.DESCRIPTION
    The environment lives in $env:USERPROFILE\.venvs\lacc rather than in a .venv
    here, because a checkout can sit inside a synchronised folder - OneDrive,
    Dropbox, iCloud. A synchroniser that reaches the environment locks files
    mid-build: `uv sync` then fails to remove the previous dist-info with
    "Access is denied", and leaves a half-removed directory behind. With
    files-on-demand it can also dehydrate .dll and .pyd files, which surfaces
    later as an import error that looks like a broken package.

    A directory junction is not enough. Synchronisers traverse reparse points,
    so a .venv junction is still walked and still locked.
    UV_PROJECT_ENVIRONMENT is enough, because then nothing belonging to the
    environment exists inside this folder at all.

    The path is derived from $env:USERPROFILE, so this file carries no personal
    path and works for any user on the machine.

.EXAMPLE
    .\run.ps1 sync
    .\run.ps1 run pytest -q
    .\run.ps1 run ruff check .
#>

# A VIRTUAL_ENV inherited from an activated shell would be reported as a mismatch on
# every command. The environment below is the one this project uses.
Remove-Item Env:VIRTUAL_ENV -ErrorAction SilentlyContinue
$env:UV_PROJECT_ENVIRONMENT = Join-Path $env:USERPROFILE ".venvs\lacc"
& uv @args
exit $LASTEXITCODE
