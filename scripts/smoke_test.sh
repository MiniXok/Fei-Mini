#!/usr/bin/env bash
set -e

echo "========================================================================"
echo "  Fei-Mini M6.2 Automated End-to-End Smoke Test"
echo "========================================================================"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
export PYTHONPATH="$PROJECT_ROOT/src"

TEMP_DB=$(mktemp /tmp/feimini_smoke_XXXXXX.db)
cleanup() {
    rm -f "$TEMP_DB"
}
trap cleanup EXIT

echo "[1/5] Creating fixture SQLite database..."
python3 -c "
import sqlite3
conn = sqlite3.connect('$TEMP_DB')
c = conn.cursor()
c.execute('CREATE TABLE customers (id INT PRIMARY KEY, name TEXT, city TEXT, balance REAL, is_vip BOOL);')
c.executemany('INSERT INTO customers VALUES (?, ?, ?, ?, ?);', [
    (1, 'Alice Zhang', 'Beijing', 1200.0, 1),
    (2, 'Bob Li', 'Shanghai', 450.0, 0),
    (3, 'Charlie Wang', 'Beijing', 3200.0, 1)
])
conn.commit()
conn.close()
"
echo "Fixture created at $TEMP_DB."

echo -e "\n[2/5] Running feimini doctor..."
python3 -m feimini.cli doctor

echo -e "\n[3/5] Testing direct natural-language query in table format..."
python3 -m feimini.cli query --db "$TEMP_DB" --question "Find all customers in Beijing" --format table

echo -e "\n[4/5] Testing query in JSON format..."
python3 -m feimini.cli query --db "$TEMP_DB" --question "Find all customers in Beijing" --format json | grep '"success": true'

echo -e "\n[5/5] Testing mutation rejection security gate..."
python3 -m feimini.cli query --db "$TEMP_DB" --question "Delete customer 1" | grep -i "prohibited"

echo -e "\n========================================================================"
echo "  All Smoke Tests Passed Successfully!"
echo "========================================================================"
