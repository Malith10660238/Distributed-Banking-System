"""
Author: Himasha Malith Amarasinghe
Student ID: 10660238
Course: CSI3344
Assignment 2 - Banking System
=======================================================
#BAS Server - Banking Application Server (Tier 2)
Final Submission - Phase 2

This server implements the business logic layer of the three-tier architecture.
It processes banking operations and delegates data persistence to the BDB Server.

TIER SEPARATION:
- Tier 1 (BC Client): User interface, connects to this server (BAS)
- Tier 2 (BAS Server): Business logic, this file, connects to BDB Server
- Tier 3 (BDB Server): Database operations only"""

import Pyro5.api
import uuid
import logging
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@Pyro5.api.expose
class BankingApplicationServer:
    """
    Banking Application Server - Tier 2
    
    This server handles business logic for banking operations:
    - User authentication and session management
    - Fee calculation based on transfer amounts
    - Transfer validation and processing
    - Delegates all database operations to BDB Server (Tier 3)
    
    Design Principle: This server knows about business rules but NOT about
    database implementation. All data operations go through BDB Server.
    """
    
    def __init__(self):
        """
        Initialize the BAS Server and connect to BDB Server.
        
        On startup, this server:
        1. Connects to BDB Server via Pyro5
        2. Initializes in-memory session storage
        3. Verifies connection to BDB Server
        """
        # In-memory session storage: {token: user_id}
        # Sessions are stored here, not in database, for performance
        # In a production system, sessions might be stored in Redis or database
        self.sessions: Dict[str, str] = {}
        
        # Connect to BDB Server
        self._connect_to_database_server()
        
        logger.info("Banking Application Server initialized")
    
    def _connect_to_database_server(self):
        """
        Connect to the BDB Server (Tier 3) via Pyro5.
        
        This establishes the connection that will be used for all database
        operations. If connection fails, server startup fails.
        """
        try:
            # Locate the name server
            ns = Pyro5.api.locate_ns()
            
            # Look up the banking database server
            uri = ns.lookup("banking.database")
            
            # Store URI for later use (don't create proxy here to avoid threading issues)
            self.bdb_server_uri = uri
            
            # Create a temporary proxy just to verify connection
            temp_proxy = Pyro5.api.Proxy(uri)
            temp_proxy.init_database()
            
            logger.info("Connected to Banking Database Server (Tier 3)")
            
        except Exception as e:
            logger.error(f"Failed to connect to BDB Server: {str(e)}")
            logger.error("Make sure bdb_server.py is running first!")
            raise
    
    def _get_bdb_server(self):
        """
        Get a fresh BDB Server proxy for the current thread.
        
        This method creates a new proxy each time to avoid "calling thread is not
        the owner" errors. Pyro5 proxies must be created in the same thread where
        they are used.
        
        Returns:
            Pyro5 proxy to BDB Server
        """
        # Create a fresh proxy in the current thread context
        # This ensures thread ownership and avoids threading errors
        return Pyro5.api.Proxy(self.bdb_server_uri)
    
    def _calculate_fee(self, amount: float) -> float:
        """
        Calculate transfer fee based on the exact fee table.
        
        FEE CALCULATION LOGIC:
        The fee structure is tiered based on transfer amount:
        - $0 – $2,000.00: 0% fee (free tier for small transfers)
        - $2,000.01 – $10,000.00: 0.25% fee (max $20.00 cap)
          Example: $5,000 transfer → $12.50 fee (0.25% of $5,000)
          Example: $10,000 transfer → $20.00 fee (capped at maximum)
        - $10,000.01 – $20,000.00: 0.20% fee (max $25.00 cap)
          Example: $15,000 transfer → $25.00 fee (capped)
        - $20,000.01 – $50,000.00: 0.125% fee (max $40.00 cap)
          Example: $30,000 transfer → $37.50 fee (0.125% of $30,000)
        - $50,000.01 – $100,000.00: 0.08% fee (max $50.00 cap)
          Example: $75,000 transfer → $50.00 fee (capped)
        - $100,000.01+: 0.05% fee (max $100.00 cap)
          Example: $150,000 transfer → $75.00 fee (0.05% of $150,000)
        
        The fee structure incentivizes smaller transfers (free under $2k)
        while charging progressively higher fees for larger amounts, with
        caps to prevent excessive fees on very large transfers.
        
        Args:
            amount: Transfer amount in dollars
            
        Returns:
            Fee amount rounded to 2 decimal places
        """
        amount = float(amount)
        
        if amount <= 0:
            return 0.00
        elif amount <= 2000.00:
            # Free tier: No fee for transfers up to $2,000
            fee = 0.00
        elif amount <= 10000.00:
            # 0.25% fee with $20 maximum
            fee = min(amount * 0.0025, 20.00)
        elif amount <= 20000.00:
            # 0.20% fee with $25 maximum
            fee = min(amount * 0.0020, 25.00)
        elif amount <= 50000.00:
            # 0.125% fee with $40 maximum
            fee = min(amount * 0.00125, 40.00)
        elif amount <= 100000.00:
            # 0.08% fee with $50 maximum
            fee = min(amount * 0.0008, 50.00)
        else:  # amount > 100000.00
            # 0.05% fee with $100 maximum
            fee = min(amount * 0.0005, 100.00)
        
        return round(fee, 2)
    
    def login(self, username: str, password: str) -> Dict:
        """
        Authenticate user and create a session token.
        
        This method:
        1. Validates credentials with BDB Server
        2. Generates a session token if valid
        3. Stores token in-memory (sessions dict)
        4. Logs the login event to audit_logs
        
        Args:
            username: User's username
            password: User's password
            
        Returns:
            Dictionary with:
            - success: bool indicating if login was successful
            - token: str session token if successful, None otherwise
            - message: str status message
        """
        logger.info(f"Login attempt for username: {username}")
        
        try:
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Validate credentials with BDB Server
            # BDB Server queries the database and returns user_id if valid
            user_id = bdb.validate_credentials(username, password)
            
            if not user_id:
                logger.warning(f"Login failed: Invalid credentials for '{username}'")
                return {
                    "success": False,
                    "token": None,
                    "message": "Invalid username or password"
                }
            
            # Generate session token using uuid4
            # UUID4 provides cryptographically random tokens, suitable for sessions
            token = str(uuid.uuid4())
            self.sessions[token] = user_id
            
            # Log login event to audit_logs
            bdb = self._get_bdb_server()
            bdb.log_event("login", user_id, f"Login successful for {username}")
            
            logger.info(f"Login successful for '{username}' (user_id: {user_id}), token: {token[:8]}...")
            return {
                "success": True,
                "token": token,
                "message": "Login successful"
            }
            
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return {
                "success": False,
                "token": None,
                "message": f"Login failed: {str(e)}"
            }
    
    def get_balance(self, token: str) -> Dict:
        """
        Get the current balance for the authenticated user.
        
        This method:
        1. Validates the session token
        2. Gets user_id from token
        3. Queries balance from BDB Server
        4. Returns balance to client
        
        WHY SYNCHRONOUS: This is a simple query that returns immediately.
        The user needs to see their balance right away, so synchronous
        request/response is appropriate. No complex processing needed.
        
        Args:
            token: Session token from login
            
        Returns:
            Dictionary with:
            - success: bool indicating if operation was successful
            - balance: float current balance if successful, None otherwise
            - message: str status message
        """
        logger.info(f"Balance request for token: {token[:8]}...")
        
        # Validate token
        if token not in self.sessions:
            logger.warning(f"Invalid token for balance request: {token[:8]}...")
            return {
                "success": False,
                "balance": None,
                "message": "Invalid or expired session token"
            }
        
        try:
            user_id = self.sessions[token]
            
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Get balance from BDB Server
            # BDB Server queries the database and returns balance
            balance = bdb.get_balance(user_id)
            
            if balance is None:
                logger.error(f"Balance not found for user_id: {user_id}")
                return {
                    "success": False,
                    "balance": None,
                    "message": "Account not found"
                }
            
            balance = round(balance, 2)
            
            logger.info(f"Balance retrieved for user {user_id}: ${balance:.2f}")
            return {
                "success": True,
                "balance": balance,
                "message": f"Current balance: ${balance:.2f}"
            }
            
        except Exception as e:
            logger.error(f"Get balance error: {str(e)}")
            return {
                "success": False,
                "balance": None,
                "message": f"Failed to get balance: {str(e)}"
            }
    
    def transfer(self, token: str, recipient_username: str, amount: float, message: str = "") -> Dict:
        """
        Transfer money from authenticated user to recipient.
        
        This method implements the complete transfer workflow:
        1. Validates session token
        2. Validates recipient exists
        3. Calculates transfer fee
        4. Validates sufficient balance
        5. Checks for duplicate transfer_id
        6. Executes transfer via BDB Server (with transaction)
        7. Logs transfer event
        
        DUPLICATE REQUEST HANDLING:
        We use a simple approach suitable for an academic system:
        - Generate transfer_id before processing
        - Check if transfer_id already exists in database
        - If exists, reject as duplicate (prevents double-processing)
        - This is simpler than complex idempotency frameworks but sufficient
          for preventing accidental duplicate transfers
        
        WHY SYNCHRONOUS: Transfers need immediate confirmation. The user
        must know right away if their transfer succeeded or failed. This
        is a critical operation that requires immediate feedback.
        
        Args:
            token: Session token from login
            recipient_username: Username of the recipient
            amount: Transfer amount in dollars
            message: Optional transfer message
            
        Returns:
            Dictionary with:
            - success: bool indicating if transfer was successful
            - transfer_id: str unique transfer ID if successful, None otherwise
            - fee: float calculated fee amount
            - message: str status message
        """
        logger.info(f"Transfer request: token={token[:8]}..., recipient={recipient_username}, amount=${amount:.2f}")
        
        # Validate token
        if token not in self.sessions:
            logger.warning(f"Invalid token for transfer: {token[:8]}...")
            return {
                "success": False,
                "transfer_id": None,
                "fee": 0.00,
                "message": "Invalid or expired session token"
            }
        
        sender_user_id = self.sessions[token]
        
        try:
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Validate recipient exists
            # BDB Server queries users table and returns user info if found
            recipient_info = bdb.get_user_by_username(recipient_username)
            
            if not recipient_info:
                logger.warning(f"Transfer failed: Recipient '{recipient_username}' not found")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": 0.00,
                    "message": f"Recipient '{recipient_username}' not found"
                }
            
            recipient_user_id = recipient_info["user_id"]
            
            # Cannot transfer to self
            if sender_user_id == recipient_user_id:
                logger.warning(f"Transfer failed: Cannot transfer to self")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": 0.00,
                    "message": "Cannot transfer money to yourself"
                }
            
            # Validate amount
            amount = float(amount)
            if amount <= 0:
                logger.warning(f"Transfer failed: Invalid amount ${amount:.2f}")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": 0.00,
                    "message": "Transfer amount must be greater than zero"
                }
            
            # Calculate fee using business logic
            fee = self._calculate_fee(amount)
            total_deduction = amount + fee
            
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Get sender balance from BDB Server
            sender_balance = bdb.get_balance(sender_user_id)
            
            if sender_balance is None:
                logger.error(f"Sender account not found: {sender_user_id}")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": fee,
                    "message": "Sender account not found"
                }
            
            # Check sufficient balance
            if sender_balance < total_deduction:
                logger.warning(f"Transfer failed: Insufficient balance. Required: ${total_deduction:.2f}, Available: ${sender_balance:.2f}")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": fee,
                    "message": f"Insufficient balance. Required: ${total_deduction:.2f} (amount: ${amount:.2f} + fee: ${fee:.2f}), Available: ${sender_balance:.2f}"
                }
            
            # Generate transfer_id for duplicate checking
            transfer_id = str(uuid.uuid4())
            
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # DUPLICATE HANDLING: Check if transfer_id already exists
            # This prevents processing the same transfer twice
            if bdb.check_transfer_exists(transfer_id):
                logger.warning(f"Duplicate transfer_id detected: {transfer_id}")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": fee,
                    "message": "Transfer already processed (duplicate request detected)"
                }
            
            # Execute transfer via BDB Server
            # BDB Server uses SQLite transaction (BEGIN/COMMIT/ROLLBACK)
            # to ensure atomicity - either all operations succeed or all fail
            success = bdb.execute_transfer(
                sender_id=sender_user_id,
                recipient_id=recipient_user_id,
                amount=amount,
                fee=fee,
                message=message,
                transfer_id=transfer_id
            )
            
            if not success:
                logger.error(f"Transfer execution failed: {transfer_id}")
                return {
                    "success": False,
                    "transfer_id": None,
                    "fee": fee,
                    "message": "Transfer execution failed. Please try again."
                }
            
            # Log transfer event to audit_logs
            bdb.log_event(
                "transfer",
                sender_user_id,
                f"Transfer ${amount:.2f} to {recipient_username}, fee: ${fee:.2f}, transfer_id: {transfer_id}"
            )
            
            logger.info(f"Transfer completed: {transfer_id}, ${amount:.2f} from {sender_user_id} to {recipient_username}, fee: ${fee:.2f}")
            
            return {
                "success": True,
                "transfer_id": transfer_id,
                "fee": fee,
                "message": f"Transfer completed successfully. Fee: ${fee:.2f}"
            }
            
        except Exception as e:
            logger.error(f"Transfer error: {str(e)}")
            return {
                "success": False,
                "transfer_id": None,
                "fee": 0.00,
                "message": f"Transfer failed: {str(e)}"
            }
    
    def get_transfer_status(self, token: str, transfer_id: str) -> Dict:
        """
        Get the status of a transfer by its ID.
        
        Args:
            token: Session token from login
            transfer_id: Unique transfer ID
            
        Returns:
            Dictionary with:
            - success: bool indicating if operation was successful
            - status: str transfer status ("COMPLETED" or "FAILED") if found, None otherwise
            - details: dict transfer details if found, None otherwise
            - message: str status message
        """
        logger.info(f"Transfer status request: token={token[:8]}..., transfer_id={transfer_id}")
        
        # Validate token
        if token not in self.sessions:
            logger.warning(f"Invalid token for transfer status: {token[:8]}...")
            return {
                "success": False,
                "status": None,
                "details": None,
                "message": "Invalid or expired session token"
            }
        
        try:
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Get transfer from BDB Server
            # BDB Server queries transfers table and returns transfer details
            transfer = bdb.get_transfer(transfer_id)
            
            if not transfer:
                logger.warning(f"Transfer not found: {transfer_id}")
                return {
                    "success": False,
                    "status": None,
                    "details": None,
                    "message": f"Transfer ID '{transfer_id}' not found"
                }
            
            # Return transfer status and details
            logger.info(f"Transfer status retrieved: {transfer_id} - {transfer.get('status')}")
            return {
                "success": True,
                "status": transfer.get("status"),
                "details": transfer,
                "message": f"Transfer status: {transfer.get('status')}"
            }
            
        except Exception as e:
            logger.error(f"Get transfer status error: {str(e)}")
            return {
                "success": False,
                "status": None,
                "details": None,
                "message": f"Failed to get transfer status: {str(e)}"
            }
    
    def request_csv_export(self, token: str) -> Dict:
        """
        Request CSV export of database tables.
        
        Only authenticated users can trigger CSV export. This method:
        1. Validates session token
        2. Calls BDB Server to export data to CSV files
        3. Returns export result
        
        Args:
            token: Session token from login
            
        Returns:
            Dictionary with success status and message
        """
        logger.info(f"CSV export request: token={token[:8]}...")
        
        # Validate token (only authenticated users can export)
        if token not in self.sessions:
            logger.warning(f"Invalid token for CSV export: {token[:8]}...")
            return {
                "success": False,
                "message": "Invalid or expired session token"
            }
        
        try:
            user_id = self.sessions[token]
            
            # Get fresh BDB Server proxy for this thread
            bdb = self._get_bdb_server()
            # Request CSV export from BDB Server
            # BDB Server exports users, accounts, and transfers to CSV files
            result = bdb.export_to_csv()
            
            # Log export event
            if result.get("success"):
                bdb.log_event(
                    "export",
                    user_id,
                    "CSV export requested and completed"
                )
            
            logger.info(f"CSV export completed: {result.get('success')}")
            return result
            
        except Exception as e:
            logger.error(f"CSV export error: {str(e)}")
            return {
                "success": False,
                "message": f"CSV export failed: {str(e)}"
            }


def main():
    """Main function to start the Pyro5 daemon and register the BankingApplicationServer."""
    try:
        # Create Pyro5 daemon
        daemon = Pyro5.api.Daemon()
        
        # Create and register BankingApplicationServer
        # Server will automatically connect to BDB Server on startup
        bas_server = BankingApplicationServer()
        uri = daemon.register(bas_server, objectId="BankingApplicationServer")
        
        # Get the name server (or use direct connection)
        ns = Pyro5.api.locate_ns()
        ns.register("banking.application", uri)
        
        logger.info(f"Banking Application Server started and registered as 'banking.application'")
        logger.info(f"Server URI: {uri}")
        logger.info("Server is ready to accept connections. Press Ctrl+C to stop.")
        
        # Start the daemon event loop
        daemon.requestLoop()
        
    except KeyboardInterrupt:
        logger.info("\nShutting down application server...")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise


if __name__ == "__main__":
    main()

