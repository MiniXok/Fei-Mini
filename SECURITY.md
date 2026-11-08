# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

---

## Security Invariants in Fei-Mini

Fei-Mini is designed with a defense-in-depth security model to ensure safe read-only database query execution:

1. **Read-Only VFS Lock:** Database connections are opened using SQLite URI parameters with `mode=ro`, denying write permissions at the operating system file descriptor boundary.
2. **Engine Pragma Lock:** `PRAGMA query_only = ON;` is executed immediately upon connection initialization.
3. **C Authorizer Callback:** All SQLite DDL (`DROP`, `ALTER`, `CREATE`), DML (`INSERT`, `UPDATE`, `DELETE`), administrative pragmas, and database attachments (`ATTACH`, `DETACH`) are intercepted and denied at parse time.
4. **Parameterized Compilation:** All literals and filter values are compiled with bound parameters (`?`). Raw user string interpolation into SQL is strictly prohibited.
5. **Instruction Progress Handler:** Monitored via `sqlite3.set_progress_handler` every 1,000 opcodes to abort infinite recursive loops and runaway queries.
6. **Pre-Execution Mutation Guard:** `SemanticIntentGuard` intercepts mutation verbs before invoking local models or planning ASTs.

---

## Reporting a Vulnerability

If you discover a security vulnerability or a potential bypass of the read-only execution harness, please notify the MiniXok security team privately rather than opening a public issue:

- **Security Contact:** **`xokmini@gmail.com`**
- **PGP/Encrypted Communication:** Available upon request.

Please include:
- A description of the vulnerability.
- Steps or a minimal SQLite database to reproduce the issue.
- Potential impact and affected versions.

We will acknowledge receipt within 48 hours and work with you to release a patch promptly.
