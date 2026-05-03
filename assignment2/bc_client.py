"""
Author: Himasha Malith Amarasinghe
Student ID: 10660238
Course: CSI3344
Assignment 2 - Banking System
=======================================================
BC Client - Banking Client (Tier 1)
Final Submission - Phase 2

This is the user interface layer of the three-tier architecture.
It provides a text-based menu interface for banking operations.

TIER SEPARATION:
- Tier 1 (BC Client): User interface, this file, connects ONLY to BAS Server
- Tier 2 (BAS Server): Business logic, connects to BDB Server
- Tier 3 (BDB Server): Database operations only"""

import Pyro5.api
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BankingClient:
    """
    Banking Client - Tier 1
    
    This client provides a text-based menu interface for banking operations.
    It connects to the BAS Server (Tier 2) via Pyro5 and never directly
    accesses the database or BDB Server.
    
    Design Principle: This client knows about user interaction but NOT about
    business logic or database implementation. All operations go through BAS Server.
    """
    
    def __init__(self):
        """Initialize the client and prepare for server connection."""
        self.server = None  # Will hold Pyro5 proxy to BAS Server
        self.token = None  # Session token after login
        self.username = None  # Logged-in username
        
    def connect(self):
        """
        Connect to the Banking Application Server (Tier 2) using Pyro5.
        
        This establishes the connection that will be used for all banking
        operations. If connection fails, client cannot proceed.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Locate the name server
            ns = Pyro5.api.locate_ns()
            
            # Look up the banking application server
            uri = ns.lookup("banking.application")
            
            # Create proxy to the application server
            # Note: We'll create fresh proxies in _get_server() to avoid threading issues
            # This initial connection is just for verification
            self.server = Pyro5.api.Proxy(uri)
            
            logger.info("Connected to Banking Application Server (Tier 2)")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}")
            print(f"\nERROR: Could not connect to Banking Application Server.")
            print(f"Make sure the following are running:")
            print(f"  1. Pyro5 nameserver: python -m Pyro5.nameserver")
            print(f"  2. BDB Server: python bdb_server.py")
            print(f"  3. BAS Server: python bas_server.py")
            print(f"\nError details: {str(e)}\n")
            return False
    
    def display_menu(self):
        """Display the main menu options based on login status."""
        print("\n" + "="*60)
        print("BANKING SYSTEM - MAIN MENU")
        print("="*60)
        if self.token:
            print(f"Logged in as: {self.username}")
            print("\n1. View Balance")
            print("2. Transfer Money")
            print("3. Check Transfer Status")
            print("4. Export Database to CSV")
            print("5. Logout")
            print("6. Exit")
        else:
            print("\n1. Login")
            print("2. Exit")
        print("="*60)
    
    def _call_server_method(self, method_name, *args, **kwargs):
        """
        Call a server method with a fresh proxy created in the same execution context.
        This ensures thread ownership and avoids "calling thread is not the owner" errors.
        
        Args:
            method_name: Name of the method to call on the server
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method
            
        Returns:
            Result from the server method call
        """
        # Create proxy in the same execution context as the method call
        # This is critical for avoiding threading issues
        ns = Pyro5.api.locate_ns()
        uri = ns.lookup("banking.application")
        server = Pyro5.api.Proxy(uri)
        
        # Get the method and call it immediately
        method = getattr(server, method_name)
        return method(*args, **kwargs)
    
    def login(self):
        """Handle user login."""
        if self.token:
            print("\nYou are already logged in. Please logout first.")
            return
        
        print("\n--- LOGIN ---")
        username = input("Username: ").strip()
        password = input("Password: ").strip()
        
        if not username or not password:
            print("ERROR: Username and password cannot be empty.")
            return
        
        try:
            # Use helper method to call server - creates proxy in same context
            # This fixes "calling thread is not the owner" errors
            result = self._call_server_method("login", username, password)
            
            if result.get("success"):
                self.token = result.get("token")
                self.username = username
                print(f"\n✓ {result.get('message')}")
                print(f"Session token: {self.token[:8]}...")
            else:
                print(f"\n✗ {result.get('message')}")
                
        except Exception as e:
            print(f"\nERROR: Login failed - {str(e)}")
            logger.error(f"Login error: {str(e)}")
    
    def logout(self):
        """Handle user logout."""
        if not self.token:
            print("\nYou are not logged in.")
            return
        
        self.token = None
        self.username = None
        print("\n✓ Logged out successfully.")
    
    def view_balance(self):
        """View the current account balance."""
        if not self.token:
            print("\nERROR: You must be logged in to view balance.")
            return
        
        try:
            # Use helper method to call server - creates proxy in same context
            result = self._call_server_method("get_balance", self.token)
            
            if result.get("success"):
                balance = result.get("balance")
                print(f"\n✓ {result.get('message')}")
                print(f"Your current balance: ${balance:.2f}")
            else:
                print(f"\n✗ {result.get('message')}")
                # Token might be invalid, clear it
                if "Invalid or expired" in result.get("message", ""):
                    self.token = None
                    self.username = None
                    
        except Exception as e:
            print(f"\nERROR: Failed to get balance - {str(e)}")
            logger.error(f"Get balance error: {str(e)}")
    
    def transfer_money(self):
        """Handle money transfer."""
        if not self.token:
            print("\nERROR: You must be logged in to transfer money.")
            return
        
        print("\n--- TRANSFER MONEY ---")
        recipient = input("Recipient username: ").strip()
        
        if not recipient:
            print("ERROR: Recipient username cannot be empty.")
            return
        
        try:
            amount_str = input("Amount ($): ").strip()
            amount = float(amount_str)
            
            if amount <= 0:
                print("ERROR: Amount must be greater than zero.")
                return
            
        except ValueError:
            print("ERROR: Invalid amount. Please enter a valid number.")
            return
        
        message = input("Transfer message (optional): ").strip()
        
        try:
            # Use helper method to call server - creates proxy in same context
            result = self._call_server_method("transfer", self.token, recipient, amount, message)
            
            if result.get("success"):
                transfer_id = result.get("transfer_id")
                fee = result.get("fee")
                print(f"\n✓ {result.get('message')}")
                print(f"Transfer ID: {transfer_id}")
                print(f"Amount transferred: ${amount:.2f}")
                print(f"Fee charged: ${fee:.2f}")
                print(f"Total deducted: ${amount + fee:.2f}")
            else:
                print(f"\n✗ {result.get('message')}")
                fee = result.get("fee", 0.00)
                if fee > 0:
                    print(f"Fee that would be charged: ${fee:.2f}")
                # Token might be invalid, clear it
                if "Invalid or expired" in result.get("message", ""):
                    self.token = None
                    self.username = None
                    
        except Exception as e:
            print(f"\nERROR: Transfer failed - {str(e)}")
            logger.error(f"Transfer error: {str(e)}")
    
    def check_transfer_status(self):
        """Check the status of a transfer."""
        if not self.token:
            print("\nERROR: You must be logged in to check transfer status.")
            return
        
        print("\n--- CHECK TRANSFER STATUS ---")
        transfer_id = input("Transfer ID: ").strip()
        
        if not transfer_id:
            print("ERROR: Transfer ID cannot be empty.")
            return
        
        try:
            # Use helper method to call server - creates proxy in same context
            result = self._call_server_method("get_transfer_status", self.token, transfer_id)
            
            if result.get("success"):
                status = result.get("status")
                details = result.get("details")
                print(f"\n✓ {result.get('message')}")
                print(f"\nTransfer Details:")
                print(f"  Transfer ID: {details.get('transfer_id')}")
                print(f"  Status: {details.get('status')}")
                print(f"  Amount: ${details.get('amount'):.2f}")
                print(f"  Fee: ${details.get('fee'):.2f}")
                print(f"  Sender ID: {details.get('sender_id')}")
                print(f"  Recipient ID: {details.get('recipient_id')}")
                if details.get('message'):
                    print(f"  Message: {details.get('message')}")
                print(f"  Timestamp: {details.get('timestamp')}")
            else:
                print(f"\n✗ {result.get('message')}")
                # Token might be invalid, clear it
                if "Invalid or expired" in result.get("message", ""):
                    self.token = None
                    self.username = None
                    
        except Exception as e:
            print(f"\nERROR: Failed to get transfer status - {str(e)}")
            logger.error(f"Get transfer status error: {str(e)}")
    
    def export_csv(self):
        """Request CSV export of database tables."""
        if not self.token:
            print("\nERROR: You must be logged in to export data.")
            return
        
        print("\n--- EXPORT DATABASE TO CSV ---")
        confirm = input("Export all database tables to CSV? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Export cancelled.")
            return
        
        try:
            # Use helper method to call server - creates proxy in same context
            result = self._call_server_method("request_csv_export", self.token)
            
            if result.get("success"):
                print(f"\n✓ {result.get('message')}")
                print("Files exported to the /exports directory:")
                print("  - users.csv")
                print("  - accounts.csv")
                print("  - transfers.csv")
            else:
                print(f"\n✗ {result.get('message')}")
                    
        except Exception as e:
            print(f"\nERROR: CSV export failed - {str(e)}")
            logger.error(f"CSV export error: {str(e)}")
    
    def run(self):
        """Main client loop."""
        print("\n" + "="*60)
        print("BANKING CLIENT - Phase 2 Final Submission")
        print("Three-Tier Architecture")
        print("="*60)
        
        # Connect to server
        if not self.connect():
            return
        
        # Main menu loop
        while True:
            try:
                self.display_menu()
                choice = input("\nEnter your choice: ").strip()
                
                if not self.token:
                    # Not logged in
                    if choice == "1":
                        self.login()
                    elif choice == "2":
                        print("\nGoodbye!")
                        break
                    else:
                        print("\nInvalid choice. Please try again.")
                else:
                    # Logged in
                    if choice == "1":
                        self.view_balance()
                    elif choice == "2":
                        self.transfer_money()
                    elif choice == "3":
                        self.check_transfer_status()
                    elif choice == "4":
                        self.export_csv()
                    elif choice == "5":
                        self.logout()
                    elif choice == "6":
                        print("\nGoodbye!")
                        break
                    else:
                        print("\nInvalid choice. Please try again.")
                
            except KeyboardInterrupt:
                print("\n\nInterrupted by user. Goodbye!")
                break
            except Exception as e:
                print(f"\nERROR: An unexpected error occurred - {str(e)}")
                logger.error(f"Unexpected error: {str(e)}")


def main():
    """Main function to start the client."""
    try:
        client = BankingClient()
        client.run()
    except Exception as e:
        print(f"\nFATAL ERROR: {str(e)}")
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

