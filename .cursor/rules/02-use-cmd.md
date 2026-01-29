---
alwaysApply: true
---

Shell policy (Windows):
- All commands must be compatible with cmd.exe.
- Never use PowerShell-specific syntax:
  - No Get-ChildItem, Set-ExecutionPolicy, $env:, ls, cat, rm, mv aliases
- Use cmd equivalents only:
  - dir, type, del, move, set VAR=value
If a command would require PowerShell, stop and ask.
