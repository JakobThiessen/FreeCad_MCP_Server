# FreeCAD MCP Server v1.1.2

Linux verification release. **No change to the server or addon code**: the bundled addon is
identical to v1.1.1 (bridge API 0.11.0, SHA-256 `5e70b47e7bc971af...`). 194 tools, reference runtime
FreeCAD 1.1.4, MCP SDK `mcp[cli]>=2.3.0,<3`.

## Highlights

- **Linux is now tested.** Ubuntu 24.04 under WSL2 with the FreeCAD 1.1.4 AppImage: the complete
  `--stage12-only` acceptance run (all 50 gates, normal mode, real MCP transport) passes, as do the
  install/update/process-loss/timeout checks (stage 12c), the PDF/SVG render checks, and a headless run on a
  virtual display (Xvfb).
- `freecad-mcp install-addon` finds the Linux addon folder (`~/.local/share/FreeCAD/v1-1/Mod`) on its own;
  `doctor` and the host tests pass on Linux (78/78).
- README: Windows/Linux badges and a new **Linux** section (AppImage setup, headless operation, test notes).

## Verification

| Platform | Check | Result |
|---|---|---|
| Linux (WSL2, Ubuntu 24.04, FreeCAD 1.1.4 AppImage, Python 3.12, mcp 2.3.0) | `--stage12-only` | **50/50**, 1 h 02 min |
| Linux | `stage12c_operations.py` (install/update, process loss, timeout) | 3/3 phases |
| Linux | `--stage10a-render` | passed |
| Linux, headless (Xvfb) | contracts, 4a, 6, 9, 10a-render, 11a, 11bc | all passed |
| Linux | host tests | 78/78 |
| Windows 11 (reference, FreeCAD 1.1.4) | `--stage12-only` | **50/50**, 1 h 44 min (also with the adjusted tests) |
| Windows | `stage12c_operations.py` | 3/3 phases (234 s) |

## Fixed (tests only)

- Stage 3 write-failure check no longer depends on a Windows file lock (`ctypes.WinDLL`); POSIX uses read-only
  permissions instead.
- Assembly gate at exactly +-90 deg offset rotation: the native solver breaks this tie differently on Windows
  (+90) and Linux (-90); both are valid mirrored solutions. The test now accepts either branch; all other
  angles are identical on both platforms.
- Stage 12c: the test wheel now includes `README.md` (required by `pyproject.toml` since 1.1.1), the old reference
  host can run on its own `mcp<2` interpreter (`FREECAD_12C_OLD_PYTHON`), and the rollback step uses the updated
  host. The install phase works again under MCP SDK 2.x. The test is now portable (`FREECAD_TEST_EXE`, process
  groups instead of single PIDs on POSIX).

## Known limits

- Linux was tested only under WSL2 with the AppImage. A native Linux machine, Flatpak, distribution packages and
  macOS are **not** tested.
- Qt's `offscreen` platform is not suitable (no OpenGL context, no screenshots). For headless use run FreeCAD on a
  virtual display (for example Xvfb).
- One earlier, non-reproducible `transaction_conflict` (a single gate in one run, 5/5 reruns and a full rerun
  passed) is unexplained; a manual interaction with the visible FreeCAD window during the run is suspected but
  unproven. Do not touch the FreeCAD window while acceptance tests run.
- FEM is excluded; CAM and BIM are not activated. Valid CAD geometry is no statement about strength or
  manufacturability.

## Install / update

```bash
pipx install freecad-mcp-server==1.1.2     # once published on PyPI
# or from the release assets:
pipx install ./freecad_mcp_server-1.1.2-py3-none-any.whl
freecad-mcp install-addon                  # close FreeCAD first; then restart FreeCAD and the MCP client
freecad-mcp doctor
```

Host and addon must be updated together. Verify the downloads with `SHA256SUMS.txt`.

## Assets

- `freecad_mcp_server-1.1.2-py3-none-any.whl`
- `freecad_mcp_server-1.1.2.tar.gz`
- `SHA256SUMS.txt`

---

## Kurzfassung (Deutsch)

Verifikations-Release fuer Linux, **keine Code-Aenderung an Server oder Addon** (Addon identisch zu v1.1.1,
Bridge-API 0.11.0). Linux ist jetzt getestet (Ubuntu 24.04 unter WSL2, FreeCAD 1.1.4 AppImage): der komplette
`--stage12-only`-Lauf (50/50 Gates), Stufe 12c (Install/Update/Prozessverlust/Timeout), die Render-Pruefungen und
ein Headless-Lauf auf virtuellem Display (Xvfb) bestehen. `install-addon` findet den Linux-Addon-Ordner selbst.
Nur Tests wurden angepasst (Stage-3-Schreibfehler portabel, Assembly-Gleichstand bei +-90 Grad, Stufe 12c).
Nicht getestet: native Linux-Maschine, Flatpak, Distributionspakete, macOS.
