# Milestone 6.0: SQLite Security & Read-Only Isolation Architecture

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Document:** `docs/M6_0_SECURITY.md`  
**Date:** 2026-11-08  

---

## 1. Multi-Layer Defense-in-Depth Architecture

Fei-Mini enforces **six independent security layers** to guarantee that user databases can never be modified, damaged, or exhausted by generated queries:

```
[Layer 1: File URI]           file:database.db?mode=ro (OS/VFS level read-only lock)
            |
[Layer 2: Engine PRAGMA]      PRAGMA query_only = ON; (SQLite engine forbids mutations)
            |
[Layer 3: SQLite Authorizer]  set_authorizer callback (Rejects write/DDL/ATTACH codes at parse time)
            |
[Layer 4: SQL Compilation]    Bound parameters exclusively (? placeholders, zero interpolation)
            |
[Layer 5: Instruction Limit]  set_progress_handler (Interrupts infinite loops & runaway queries)
            |
[Layer 6: Output Boundary]    max_rows & max_bytes bounds (Prevents memory exhaustion)
```

---

## 2. Layer Specifications

### Layer 1: Read-Only URI Mode
All database connections are established via SQLite URI format: `file:{abs_path}?mode=ro`. The SQLite VFS denies write locks at the operating system file descriptor boundary.

### Layer 2: `PRAGMA query_only = ON`
Executed immediately upon connection initialization. SQLite rejects any attempt to execute statements that modify the database, even if write permissions existed.

### Layer 3: SQLite Authorizer Callback (`set_authorizer`)
Implemented via C library action callback `_strict_readonly_authorizer`.
- **Allowed Actions:** `SQLITE_SELECT` (21), `SQLITE_READ` (20), `SQLITE_FUNCTION` (19), `SQLITE_RECURSIVE` (33).
- **Explicitly Denied Actions (Immediate `SQLITE_DENY`):**
  - Data Manipulation: `SQLITE_INSERT`, `SQLITE_UPDATE`, `SQLITE_DELETE`.
  - Schema Modification: `SQLITE_CREATE_TABLE`, `SQLITE_DROP_TABLE`, `SQLITE_ALTER_TABLE`, `SQLITE_CREATE_INDEX`, `SQLITE_DROP_INDEX`, `SQLITE_CREATE_VIEW`, `SQLITE_DROP_VIEW`.
  - External Attachment: `SQLITE_ATTACH`, `SQLITE_DETACH`.
  - Administrative Pragmas: `SQLITE_PRAGMA`.

### Layer 4: Parameterized Value Binding
The compiler (`MiniRelSQLCompiler`) generates parameterized SQL with `?` placeholders for all literals, integers, floats, and strings. Identifiers (table names and column names) are validated against inspected schema metadata and escaped with double quotes (`"table"."col"`). Raw user string interpolation is strictly prohibited.

### Layer 5: Instruction-Level Progress Handler
Queries are monitored via `sqlite3.set_progress_handler(check_progress, 1000)`. Every 1,000 SQLite virtual machine instructions, the handler checks elapsed wall-clock time. If the timeout threshold is exceeded, the handler returns non-zero, immediately aborting execution with `SQLiteTimeoutError`.

### Layer 6: Output Cardinality and Memory Cap
Results are fetched in batches of 100 rows. Execution halts with truncation flag (`is_truncated = True`) if rows reach `max_rows` (default 10,000) or serialized bytes reach `max_bytes` (default 10 MB).

---

## 3. Empirical Security Verification

Automated security tests (`tests/sqlite/test_security.py`) verify:
1. `INSERT`, `UPDATE`, `DELETE` queries raise `SQLiteSecurityError`.
2. `DROP TABLE`, `CREATE TABLE`, `ALTER TABLE`, and `ATTACH DATABASE` raise `SQLiteSecurityError`.
3. **Database File Hash Invariant:** The cryptographic SHA-256 hash of the SQLite database file before and after malicious execution attempts is identical (`test_database_hash_invariant_preserved`).
4. Recursive runaway queries (`WITH RECURSIVE cnt(x) ...`) are aborted at $50\text{ ms}$ via progress handler (`test_query_progress_handler_timeout_interruption`).
