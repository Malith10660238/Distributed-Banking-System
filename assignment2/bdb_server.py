"""
Author: Himasha Malith Amarasinghe
Student ID: 10660238
Course: CSI3344
Assignment 2 - Banking System
=======================================================
BDB Server - Banking Database Server (Tier 3)
Final Submission - Phase 2

This is the ONLY file that directly interacts with the SQLite database.
It provides database operations as a Pyro5 service, maintaining strict
separation of concerns in the three-tier architecture.


This file is the ONLY one that:
- Imports sqlite3
- Accesses bank.db directly
- Contains SQL queries
"""

import Pyro5.api
import sqlite3
import logging
import csv
import os
import signal
import sys
from datetime import datetime
from typing import Optional, Dict, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), "database", "bank.db")
EXPORTS_DIR = os.path.join(os.path.dirname(__file__), "exports")


@Pyro5.api.expose
class BankingDatabaseServer:
    """
    Banking Database Server - Tier 3
    
    This server handles ALL database operations for the banking system.
    It exposes methods via Pyro5 that can be called by the BAS Server (Tier 2).
    
    Design Principle: This is the ONLY component that knows about SQLite.
    All other tiers communicate with the database through this server.
    """
    
    def __init__(self):
        """Initialize the database server and ensure database exists."""
        # Ensure exports directory exists
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        
        # Initialize database (create tables and mock data if needed)
        self.init_database()
        logger.info("Banking Database Server initialized")
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Create and return a database connection.
        
        Returns:
            sqlite3.Connection: Database connection object
        """
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    def init_database(self) -> None:
        """
        Initialize the database schema and insert mock users if database is empty.
        
        This method:
        1. Creates all required tables if they don't exist
        2. Inserts mock users (alice and bob) if the database is empty
        
        Called automatically on server startup.
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL
                )
            """)
            
            # Create accounts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accounts (
                    account_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    balance REAL NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Create transfers table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transfers (
                    transfer_id TEXT PRIMARY KEY,
                    sender_id TEXT NOT NULL,
                    recipient_id TEXT NOT NULL,
                    amount REAL NOT NULL,
                    fee REAL NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (sender_id) REFERENCES users(user_id),
                    FOREIGN KEY (recipient_id) REFERENCES users(user_id)
                )
            """)
            
            # Create audit_logs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    user_id TEXT,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            
            conn.commit()
            logger.info("Database tables created/verified")
            
            # Check if database is empty (no users exist)
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()["count"]
            
            if user_count == 0:
                # Insert mock users
                # User 1: Alice
                cursor.execute("""
                    INSERT INTO users (user_id, username, password)
                    VALUES (?, ?, ?)
                """, ("user_001", "alice", "pass123"))
                
                cursor.execute("""
                    INSERT INTO accounts (account_id, user_id, balance)
                    VALUES (?, ?, ?)
                """, ("acc_001", "user_001", 10000.00))
                
                # User 2: Bob
                cursor.execute("""
                    INSERT INTO users (user_id, username, password)
                    VALUES (?, ?, ?)
                """, ("user_002", "bob", "pass456"))
                
                cursor.execute("""
                    INSERT INTO accounts (account_id, user_id, balance)
                    VALUES (?, ?, ?)
                """, ("acc_002", "user_002", 5000.00))
                
                conn.commit()
                logger.info("Mock users initialized: alice ($10,000) and bob ($5,000)")
            else:
                logger.info(f"Database already contains {user_count} user(s)")
                
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {str(e)}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def validate_credentials(self, username: str, password: str) -> Optional[str]:
        """
        Validate user credentials against the database.
        
        Args:
            username: Username to validate
            password: Password to validate
            
        Returns:
            user_id if credentials are valid, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id FROM users
                WHERE username = ? AND password = ?
            """, (username, password))
            
            result = cursor.fetchone()
            
            if result:
                user_id = result["user_id"]
                logger.info(f"Credentials validated for user_id: {user_id}")
                return user_id
            else:
                logger.warning(f"Invalid credentials for username: {username}")
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error validating credentials: {str(e)}")
            return None
        finally:
            conn.close()
    
    def get_balance(self, user_id: str) -> Optional[float]:
        """
        Get the current balance for a user.
        
        WHY SYNCHRONOUS: This is a simple query that returns immediately.
        The user needs to see their balance right away, so synchronous
        request/response is appropriate. No complex processing needed.
        
        Args:
            user_id: User ID to get balance for
            
        Returns:
            Balance as float if user exists, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT balance FROM accounts
                WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            
            if result:
                balance = float(result["balance"])
                logger.info(f"Balance retrieved for {user_id}: ${balance:.2f}")
                return balance
            else:
                logger.warning(f"No account found for user_id: {user_id}")
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting balance: {str(e)}")
            return None
        finally:
            conn.close()
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """
        Get user information by username.
        
        Args:
            username: Username to look up
            
        Returns:
            Dictionary with user_id and username if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT user_id, username FROM users
                WHERE username = ?
            """, (username,))
            
            result = cursor.fetchone()
            
            if result:
                user_info = {
                    "user_id": result["user_id"],
                    "username": result["username"]
                }
                logger.info(f"User found: {username} -> {result['user_id']}")
                return user_info
            else:
                logger.warning(f"User not found: {username}")
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting user: {str(e)}")
            return None
        finally:
            conn.close()
    
    def check_transfer_exists(self, transfer_id: str) -> bool:
        """
        Check if a transfer with the given ID already exists.
        
        Used for duplicate request handling - prevents processing the same
        transfer twice.
        
        Args:
            transfer_id: Transfer ID to check
            
        Returns:
            True if transfer exists, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT COUNT(*) as count FROM transfers
                WHERE transfer_id = ?
            """, (transfer_id,))
            
            result = cursor.fetchone()
            exists = result["count"] > 0
            
            if exists:
                logger.warning(f"Duplicate transfer_id detected: {transfer_id}")
            
            return exists
                
        except sqlite3.Error as e:
            logger.error(f"Error checking transfer existence: {str(e)}")
            return False
        finally:
            conn.close()
    
    def execute_transfer(self, sender_id: str, recipient_id: str, amount: float,
                        fee: float, message: str, transfer_id: str) -> bool:
        """
        Execute a money transfer using a database transaction.
        
        WHY SYNCHRONOUS: Transfers need immediate confirmation. The user
        must know right away if their transfer succeeded or failed. This
        is a critical operation that requires immediate feedback.
        
        WHY SQLITE TRANSACTIONS: We use BEGIN/COMMIT/ROLLBACK to ensure
        ACID properties:
        - Atomicity: Either all operations succeed or all fail
        - Consistency: Database remains in valid state
        - Isolation: Concurrent transfers don't interfere
        - Durability: Once committed, changes are permanent
        
        If ANY step fails (insufficient balance, constraint violation, etc.),
        the entire transaction is rolled back, ensuring data integrity.
        
        Args:
            sender_id: User ID of the sender
            recipient_id: User ID of the recipient
            amount: Transfer amount (without fee)
            fee: Transfer fee
            message: Optional transfer message
            transfer_id: Unique transfer ID
            
        Returns:
            True if transfer executed successfully, False otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Begin transaction
            cursor.execute("BEGIN TRANSACTION")
            
            # Get sender balance
            cursor.execute("""
                SELECT balance FROM accounts
                WHERE user_id = ?
            """, (sender_id,))
            sender_result = cursor.fetchone()
            
            if not sender_result:
                logger.error(f"Sender account not found: {sender_id}")
                conn.rollback()
                return False
            
            sender_balance = float(sender_result["balance"])
            total_deduction = amount + fee
            
            # Verify sufficient balance (double-check, though BAS should have checked)
            if sender_balance < total_deduction:
                logger.error(f"Insufficient balance: {sender_id} has ${sender_balance:.2f}, needs ${total_deduction:.2f}")
                conn.rollback()
                return False
            
            # Deduct amount + fee from sender
            new_sender_balance = sender_balance - total_deduction
            cursor.execute("""
                UPDATE accounts
                SET balance = ?
                WHERE user_id = ?
            """, (round(new_sender_balance, 2), sender_id))
            
            # Get recipient balance
            cursor.execute("""
                SELECT balance FROM accounts
                WHERE user_id = ?
            """, (recipient_id,))
            recipient_result = cursor.fetchone()
            
            if not recipient_result:
                logger.error(f"Recipient account not found: {recipient_id}")
                conn.rollback()
                return False
            
            recipient_balance = float(recipient_result["balance"])
            
            # Add amount to recipient (fee is NOT added to recipient)
            new_recipient_balance = recipient_balance + amount
            cursor.execute("""
                UPDATE accounts
                SET balance = ?
                WHERE user_id = ?
            """, (round(new_recipient_balance, 2), recipient_id))
            
            # Insert transfer record
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO transfers (
                    transfer_id, sender_id, recipient_id, amount, fee,
                    status, message, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (transfer_id, sender_id, recipient_id, round(amount, 2),
                  round(fee, 2), "COMPLETED", message, timestamp))
            
            # Commit transaction
            conn.commit()
            
            logger.info(f"Transfer executed: {transfer_id}, ${amount:.2f} from {sender_id} to {recipient_id}, fee: ${fee:.2f}")
            return True
            
        except sqlite3.Error as e:
            logger.error(f"Transfer execution error: {str(e)}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_transfer(self, transfer_id: str) -> Optional[Dict]:
        """
        Get transfer details by transfer ID.
        
        Args:
            transfer_id: Transfer ID to look up
            
        Returns:
            Dictionary with transfer details if found, None otherwise
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT transfer_id, sender_id, recipient_id, amount, fee,
                       status, message, timestamp
                FROM transfers
                WHERE transfer_id = ?
            """, (transfer_id,))
            
            result = cursor.fetchone()
            
            if result:
                transfer = {
                    "transfer_id": result["transfer_id"],
                    "sender_id": result["sender_id"],
                    "recipient_id": result["recipient_id"],
                    "amount": float(result["amount"]),
                    "fee": float(result["fee"]),
                    "status": result["status"],
                    "message": result["message"],
                    "timestamp": result["timestamp"]
                }
                logger.info(f"Transfer retrieved: {transfer_id}")
                return transfer
            else:
                logger.warning(f"Transfer not found: {transfer_id}")
                return None
                
        except sqlite3.Error as e:
            logger.error(f"Error getting transfer: {str(e)}")
            return None
        finally:
            conn.close()
    
    def log_event(self, event_type: str, user_id: Optional[str], message: str) -> None:
        """
        Log an event to the audit_logs table.
        
        Args:
            event_type: Type of event (e.g., "login", "transfer", "export")
            user_id: User ID associated with the event (can be None)
            message: Event message
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            timestamp = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO audit_logs (event_type, user_id, message, timestamp)
                VALUES (?, ?, ?, ?)
            """, (event_type, user_id, message, timestamp))
            
            conn.commit()
            logger.debug(f"Event logged: {event_type} for {user_id}")
            
        except sqlite3.Error as e:
            logger.error(f"Error logging event: {str(e)}")
            conn.rollback()
        finally:
            conn.close()
    
    def export_to_csv(self) -> Dict:
        """
        Export database tables to CSV files in the /exports directory.
        
        This is the PRIMARY export method triggered manually via BC Client menu.
        Flow: BC Client → BAS Server → BDB Server → CSV files
        
        Exports three tables:
        - users.csv: user_id, username, password
        - accounts.csv: account_id, user_id, balance
        - transfers.csv: transfer_id, sender_id, recipient_id, amount, fee, status, message, timestamp
        
        Error Handling:
        - If directory creation fails, returns error immediately
        - If one CSV file fails, continues exporting other files
        - Returns success if at least one file is exported successfully
        
        Returns:
            Dictionary with success status and message
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # Step 1: Create /exports/ directory if not exists
            # This ensures the directory exists before attempting to write files
            try:
                os.makedirs(EXPORTS_DIR, exist_ok=True)
            except OSError as e:
                error_msg = f"Failed to create exports directory: {str(e)}"
                logger.error(error_msg)
                return {
                    "success": False,
                    "message": error_msg
                }
            
            # Track export results
            export_results = {
                "users": False,
                "accounts": False,
                "transfers": False
            }
            export_counts = {
                "users": 0,
                "accounts": 0,
                "transfers": 0
            }
            errors = []
            
            # Step 2: Export users table
            try:
                cursor.execute("SELECT user_id, username, password FROM users")
                users = cursor.fetchall()
                
                users_file = os.path.join(EXPORTS_DIR, "users.csv")
                with open(users_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["user_id", "username", "password"])
                    for user in users:
                        writer.writerow([user["user_id"], user["username"], user["password"]])
                
                export_results["users"] = True
                export_counts["users"] = len(users)
                logger.info(f"Exported {len(users)} users to users.csv")
                
            except Exception as e:
                error_msg = f"Failed to export users: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Step 3: Export accounts table
            try:
                cursor.execute("SELECT account_id, user_id, balance FROM accounts")
                accounts = cursor.fetchall()
                
                accounts_file = os.path.join(EXPORTS_DIR, "accounts.csv")
                with open(accounts_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["account_id", "user_id", "balance"])
                    for account in accounts:
                        writer.writerow([account["account_id"], account["user_id"], account["balance"]])
                
                export_results["accounts"] = True
                export_counts["accounts"] = len(accounts)
                logger.info(f"Exported {len(accounts)} accounts to accounts.csv")
                
            except Exception as e:
                error_msg = f"Failed to export accounts: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Step 4: Export transfers table
            try:
                cursor.execute("""
                    SELECT transfer_id, sender_id, recipient_id, amount, fee,
                           status, message, timestamp
                    FROM transfers
                """)
                transfers = cursor.fetchall()
                
                transfers_file = os.path.join(EXPORTS_DIR, "transfers.csv")
                with open(transfers_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["transfer_id", "sender_id", "recipient_id", "amount",
                                   "fee", "status", "message", "timestamp"])
                    for transfer in transfers:
                        writer.writerow([
                            transfer["transfer_id"],
                            transfer["sender_id"],
                            transfer["recipient_id"],
                            transfer["amount"],
                            transfer["fee"],
                            transfer["status"],
                            transfer["message"] if transfer["message"] else "",
                            transfer["timestamp"]
                        ])
                
                export_results["transfers"] = True
                export_counts["transfers"] = len(transfers)
                logger.info(f"Exported {len(transfers)} transfers to transfers.csv")
                
            except Exception as e:
                error_msg = f"Failed to export transfers: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
            
            # Step 5: Determine overall success and create message
            success_count = sum(1 for v in export_results.values() if v)
            
            if success_count == 0:
                # All exports failed
                logger.error("CSV export failed: All files failed to export")
                return {
                    "success": False,
                    "message": f"Export failed. Errors: {'; '.join(errors)}"
                }
            elif success_count == 3:
                # All exports succeeded
                logger.info(f"CSV export completed: {export_counts['users']} users, {export_counts['accounts']} accounts, {export_counts['transfers']} transfers")
                return {
                    "success": True,
                    "message": f"Export successful. Files saved to {EXPORTS_DIR}: users.csv ({export_counts['users']} rows), accounts.csv ({export_counts['accounts']} rows), transfers.csv ({export_counts['transfers']} rows)"
                }
            else:
                # Partial success
                successful_files = [k for k, v in export_results.items() if v]
                failed_files = [k for k, v in export_results.items() if not v]
                logger.warning(f"CSV export partially successful. Succeeded: {successful_files}, Failed: {failed_files}")
                return {
                    "success": True,  # Partial success is still considered success
                    "message": f"Export partially successful. Exported: {', '.join([f'{f}.csv' for f in successful_files])}. Failed: {', '.join([f'{f}.csv' for f in failed_files])}. Errors: {'; '.join(errors)}"
                }
            
        except Exception as e:
            logger.error(f"CSV export error: {str(e)}")
            return {
                "success": False,
                "message": f"Export failed: {str(e)}"
            }
        finally:
            conn.close()


def main():
    """
    Main function to start the Pyro5 daemon and register the BankingDatabaseServer.
    
    Includes automatic CSV export on shutdown (Ctrl+C) as a bonus feature.
    """
    # Global variable to hold server instance for shutdown handler
    global db_server_instance
    
    def shutdown_handler(signum, frame):
        """
        Signal handler for graceful shutdown with automatic CSV export.
        
        This is a BONUS feature that attempts to export data automatically
        when the server receives SIGINT (Ctrl+C). This is best-effort only
        and may not work if the process is killed forcefully (SIGKILL).
        
        Best effort - may not work if process killed forcefully.
        """
        logger.info("\nShutdown signal received. Attempting automatic CSV export...")
        
        try:
            # Attempt automatic export before shutdown
            if 'db_server_instance' in globals() and db_server_instance:
                result = db_server_instance.export_to_csv()
                if result.get("success"):
                    logger.info("Automatic CSV export completed successfully before shutdown.")
                else:
                    logger.warning(f"Automatic CSV export failed: {result.get('message')}")
            else:
                logger.warning("Server instance not available for automatic export.")
        except Exception as e:
            logger.error(f"Error during automatic CSV export: {str(e)}")
        
        logger.info("Shutting down database server...")
        sys.exit(0)
    
    try:
        # Register signal handler for SIGINT (Ctrl+C)
        # This enables automatic export on shutdown
        signal.signal(signal.SIGINT, shutdown_handler)
        
        # Create Pyro5 daemon
        daemon = Pyro5.api.Daemon()
        
        # Create and register BankingDatabaseServer
        db_server_instance = BankingDatabaseServer()
        uri = daemon.register(db_server_instance, objectId="BankingDatabaseServer")
        
        # Get the name server (or use direct connection)
        ns = Pyro5.api.locate_ns()
        ns.register("banking.database", uri)
        
        logger.info(f"Banking Database Server started and registered as 'banking.database'")
        logger.info(f"Server URI: {uri}")
        logger.info(f"Database location: {DB_PATH}")
        logger.info("Server is ready to accept connections. Press Ctrl+C to stop.")
        logger.info("Note: Automatic CSV export will be attempted on shutdown (best effort).")
        
        # Start the daemon event loop
        daemon.requestLoop()
        
    except KeyboardInterrupt:
        # This should be handled by signal handler, but kept as fallback
        logger.info("\nShutting down database server...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise


if __name__ == "__main__":
    main()

