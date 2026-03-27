# Packaging

## Encoding

- Text encoding: `UTF-8`
- Line endings: `LF`

## Install Build Dependency

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
```

## Build Windows EXE

```powershell
.\scripts\build_exe.ps1
```

Build output:

- `dist/R6TacticsBoard/`

## Notes

- The build script uses `--windowed`, so the packaged app does not open a console window.
- `src/assets/` is bundled into the output directory as `assets/` and remains editable after packaging.
- Project files now save map paths relative to the project file when possible, which makes moving a project folder easier.
