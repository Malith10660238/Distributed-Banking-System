========================================
CSI3344 ASSIGNMENT 2 - BANKING SYSTEM (Phase 2)
THREE-TIER DISTRIBUTED SYSTEM - 10660238 - Himasha Malith Amarasinghe
========================================

1. SYSTEM OVERVIEW

This is a three-tier distributed banking system:
- Tier 1: BC Client (Banking Client)
- Tier 2: BAS Server (Bank Application Server)
- Tier 3: BDB Server (Bank Database Server)

Technology: Python 3.8+ with Pyro5 RPC, SQLite database

DEVELOPMENT NOTE:
Phase 1 (two-tier) was used as an intermediate development step.
This submission contains only Phase 2 (three-tier).

2. ARCHITECTURE

ASCII Diagram:
┌─────────────┐
│  BC Client  │  (Text-based menu)
└──────┬──────┘
       │ Pyro5 RPC
       ↓
┌─────────────┐
│ BAS Server  │  (Business logic, authentication, fee calculation)
└──────┬──────┘
       │ Pyro5 RPC
       ↓
┌─────────────┐
│ BDB Server  │  (Database operations only)
└──────┬──────┘
       │ Direct access
       ↓
   [bank.db]
   SQLite

TIER SEPARATION RULES:
- BC Client: Never accesses BDB Server or SQLite
- BAS Server: Never accesses SQLite directly
- BDB Server: ONLY component that touches SQLite

3. REQUIREMENTS

Software:
- Python 3.8 or higher
- Pyro5 library

Installation:
pip install Pyro5

Files needed:
- bc_client.py
- bas_server.py
- bdb_server.py

4. SETUP AND RUNNING

IMPORTANT: Start components in this exact order!

Step 1: Start Pyro Name Server
Command: python -m Pyro5.nameserver
Leave this running in its own terminal

Step 2: Start BDB Server
Command: python bdb_server.py
This creates bank.db and initializes mock data
Leave running

Step 3: Start BAS Server
Command: python bas_server.py
This connects to BDB Server
Leave running

Step 4: Run BC Client
Command: python bc_client.py
This is the user interface

TROUBLESHOOTING:
- "Cannot locate nameserver" → Start nameserver first
- "Cannot connect to BDB" → Start BDB before BAS
- "Connection refused" → Check all servers are running

5. MOCK USER ACCOUNTS

Two users are pre-loaded:

Username: alice
Password: pass123
Balance: $10,000.00

Username: bob  
Password: pass456
Balance: $5,000.00

6. MENU OPTIONS

1. Login - Enter username and password
2. View Balance - Shows current account balance
3. Transfer Money - Send money to another user
4. Check Transfer Status - Query transfer by ID
5. Export Database to CSV - Save data to /exports/ folder
6. Logout - Clear session
7. Exit - Close client

7. TRANSFER FEE TABLE

Amount Range              Fee Rate    Maximum Fee
$0 – $2,000              0%          $0 (Free)
$2,000.01 – $10,000      0.25%       $20
$10,000.01 – $20,000     0.20%       $25
$20,000.01 – $50,000     0.125%      $40
$50,000.01 – $100,000    0.08%       $50
$100,000.01+             0.05%       $100

Examples:
- Transfer $1,500 → Fee $0
- Transfer $5,000 → Fee $12.50 (0.25% of $5,000)
- Transfer $150,000 → Fee $75 (0.05% of $150,000, under $100 cap)

8. TEST SCENARIOS

Test Case 1: Successful Transfer (Free Tier)
- Login as alice
- Transfer $1,500 to bob
- Expected: Fee $0, success message

Test Case 2: Transfer with Fee (Entry Tier)
- Login as alice
- Transfer $5,000 to bob
- Expected: Fee $12.50, total deducted $5,012.50

Test Case 3: Transfer with Capped Fee (Top Tier)
- Login as alice (needs sufficient balance)
- Transfer $150,000 to bob
- Expected: Fee $75 (0.05% but under $100 cap)

Test Case 4: Insufficient Balance
- Login as bob
- Try to transfer $10,000 (balance insufficient)
- Expected: Error message, no money moved

Test Case 5: Invalid Recipient
- Login as alice
- Try to transfer to "charlie" (doesn't exist)
- Expected: Error message

Test Case 6: Duplicate Transfer Prevention
- Complete a transfer
- Try using same credentials again
- Expected: System prevents duplicate

Test Case 7: Check Transfer Status
- Complete a transfer, note transfer_id
- Use menu option 4 to check status
- Expected: Shows "COMPLETED" status with details

Test Case 8: CSV Export
- Use menu option 5
- Check /exports/ folder
- Expected: users.csv, accounts.csv, transfers.csv created

Test Case 9: Persistence Check
- Complete several transfers
- Stop and restart all servers
- Login and check balance
- Expected: All data persists correctly

9. DATABASE LOCATION

File: /database/bank.db
Created automatically on first run

To view database (optional):
- Download "DB Browser for SQLite"
- Open bank.db
- View tables: users, accounts, transfers, audit_logs

10. CSV EXPORTS

Location: /exports/
Files: users.csv, accounts.csv, transfers.csv

When exported:
- Manually via menu option 5 (recommended)
- Automatically on BDB Server shutdown (best effort)

Submit these CSV files with your assignment.

11. STOPPING THE SYSTEM

1. Exit BC Client (menu option 7)
2. Stop BAS Server (Ctrl+C)
3. Stop BDB Server (Ctrl+C) - triggers CSV export
4. Stop Name Server (Ctrl+C)

12. PROJECT STRUCTURE

assignment2/
  bc_client.py       - User interface
  bas_server.py      - Application logic
  bdb_server.py      - Database operations
  /database/
    bank.db          - SQLite database (created at runtime)
  /exports/
    users.csv        - Exported after running
    accounts.csv
    transfers.csv
  README.txt         - This file

13. SUBMISSION CHECKLIST

Include in .zip file:
✓ bc_client.py
✓ bas_server.py
✓ bdb_server.py
✓ README.txt
✓ Project report (separate .docx/.pdf)
✓ /exports/ folder with CSV files (after testing)

14. NOTES FOR MARKERS

- All monetary values rounded to 2 decimal places
- System uses token-based authentication
- Transfers are atomic (SQLite transactions)
- Duplicate transfers handled by checking existing transfer_ids
- System runs without IDE (command line only)
- Phase 1 code not included (development step only)

========================================
END OF README
========================================
