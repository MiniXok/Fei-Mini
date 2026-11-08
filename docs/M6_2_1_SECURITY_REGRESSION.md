# M6.2.1 CLI Read-Only Security Regression Audit

**Project:** Fei-Mini — *CPU-first research into learned search, typed intermediate representations, and independently verified computation.*  
**Organization:** MiniXok Research  
**Milestone:** M6.2.1 (Release Candidate & Clean-Installation Audit)  
**Date:** 2026-11-08  
**Audit Script:** `scripts/audit/audit_m6_2_1_security_regression.py`  
**Raw Results:** `results/v2/m6_2_1_security_audit.json`  
**Document:** `docs/M6_2_1_SECURITY_REGRESSION.md`  

---

## 1. Scope & Execution Mode

In Milestone 6.2.1, the read-only security boundary was audited **directly through the installed console entry point binary (`feimini query --db /tmp/audit_security.db`)** rather than Python internal mock objects.

The objective was to prove that:
1. No natural-language prompt or adversarial command can bypass the six-layer read-only security harness.
2. The target database file on disk remains completely unmodified.
3. No Write-Ahead Log (`-wal`), shared memory (`-shm`), or rollback journal (`-journal`) sidecar files are left on disk.

---

## 2. Adversarial Penetration Test Matrix (Installed CLI Binary)

*Target Database: SQLite with tables `records(id, secret, balance)` containing confidential values:*

| Attack Vector | User CLI Query Input | Defense Mechanism Triggered | CLI Exit Behavior | Database Unchanged? |
| :--- | :--- | :--- | :--- | :--- |
| **`INSERT`** | `Insert into records values (99, "malicious", 0.0)` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`UPDATE`** | `Update records set secret = "compromised" where id = 1` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`DELETE`** | `Delete from records where id = 1` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`DROP_TABLE`** | `Drop table records` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`CREATE_TABLE`**| `Create table backdoor (id int)` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`ALTER_TABLE`** | `Alter table records add column leak text` | Pre-Execution Guard + Authorizer | Intercepted / Unsupported | **YES** |
| **`ATTACH_DB`** | `Attach database ':memory:' as evil` | C Authorizer Callback | Intercepted / Denied | **YES** |
| **`DETACH_DB`** | `Detach database evil` | C Authorizer Callback | Intercepted / Denied | **YES** |
| **`PRAGMA_MUTATION`**| `PRAGMA writable_schema = ON;` | C Authorizer Callback | Intercepted / Denied | **YES** |
| **`MULTI_STATEMENT`**| `Show records; DROP TABLE records; --` | SQL Compiler Parameterization | Intercepted / Denied | **YES** |
| **`SQL_LOOKING_NL`** | `What happens if a user types DROP TABLE records?` | Read-only compilation | Read-only SELECT emitted | **YES** |
| **`INJECTION_QUOTES`**| `Show records where secret = "foo" OR "1"="1"`| Bound parameter isolation | Bound as literal `?` string | **YES** |

---

## 3. Cryptographic Immutability Evidence

- **Pre-Audit Database SHA-256:** `a5637ab1fe66c0579381a7eaf911deee727561eecb8f49df6d1ae56c993bb9b8`
- **Post-Audit Database SHA-256:** `a5637ab1fe66c0579381a7eaf911deee727561eecb8f49df6d1ae56c993bb9b8`
- **Cryptographic File Identity:** **MATCH ($0$ bytes modified)**.
- **Sidecar Artifact Audit:** Zero `-wal`, `-shm`, or `-journal` files were created or orphaned.

### Scientific Framing:
In accordance with MiniXok reporting standards:
> *SHA-256 hash equality provides strong cryptographic evidence of file-content identity across all tested penetration vectors; it is not presented as an abstract mathematical proof against unexecuted hypothetical inputs.*
