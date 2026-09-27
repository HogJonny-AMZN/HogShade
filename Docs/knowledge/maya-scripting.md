# Maya 2026 scripting in HogShade

**Status:** Living. Topic file of the knowledge base; the lessons from the E1 check, the naga spike and
the Maya shell (PR F, PR G), moved from the decision log on 2026-09-27. `tools/maya/_session.py` is
where most of them are encoded; `tools/README.md` says how to run the checks; the orchestrator route
is in [job-orchestrator.md](job-orchestrator.md).

- Maya's Python is 3.11: no nested same-quote f-strings; parse-check scripts with `mayapy` first.
- Run checks with a scratch `MAYA_APP_DIR` and `MAYA_VP2_DEVICE_OVERRIDE=VirtualDeviceDx11`; the
  owner's viewport preference is OpenGL Core and is never changed.
- Playblast with `offScreen=False`; the offscreen path does not draw the dx11 effect. Compare
  frames on decoded BMP pixels over the non-background region; `MImage` pixel access runs out of
  memory.
- Exit code 127 after `quit` is normal; 139 at about twelve seconds is a startup crash, so wrap
  launches in a retry loop, kill stray `maya.exe` and `mayapy` first, and never run two Maya
  instances at once.
- `dx11Shader` texture slots need a connected `file` node (`setAttr` with a string fails); lights
  are bound explicitly with `cmds.dx11Shader(node, connectLight=("Light 0", light_transform))`
  and read back with `lightConnectionStatus`; the `-e` flag is invalid on that command.
- Legacy v2 findings (never re-chase): both cube parameters use the `environment` semantic; unbound
  2D maps sample black, so an unbound cavity map blacks out specular; RGBM `.bgr` decode at
  exposure 5 and gamma 2.23. All addressed by the port's deviations.
- A resident worker keeps the previous check's scene and any file the check opened: start every
  check with `cmds.file(new=True, force=True)` and stop Script Editor history mirroring at the end
  (`Docs/standards/failure-modes.md`, entry 7).
- A path built from a job parameter (`check`, `variant`) refuses `..` and anything outside the
  verification root before it is created (entry 9).
