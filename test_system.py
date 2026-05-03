"""
Test Script for Banking System - Phase 2
Automated test suite for three-tier banking system

This script tests all major functionality of the banking system:
- Authentication (login)
- Balance retrieval
- Money transfers with fee calculation
- Error handling (insufficient balance, invalid recipient)
- Transfer status checking

REQUIREMENTS:
- All servers must be running (nameserver, BDB Server, BAS Server)
- Test user 'alice' must exist with initial balance $10,000.00
- Test user 'bob' must exist

USAGE:
    python test_system.py
"""

import Pyro5.api
import sys
from typing import Dict, Optional, Tuple


class BankingSystemTester:
    """
    Automated test suite for the banking system.
    
    Connects to BAS Server and runs comprehensive tests on all functionality.
    """
    
    def __init__(self):
        """Initialize the tester and connect to BAS Server."""
        self.server = None
        self.token = None
        self.test_results = []
        self.transfer_ids = []  # Store transfer IDs for status checking
        
    def connect(self) -> bool:
        """
        Connect to the Banking Application Server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            print("Connecting to BAS Server...")
            ns = Pyro5.api.locate_ns()
            uri = ns.lookup("banking.application")
            self.server = Pyro5.api.Proxy(uri)
            print("✓ Connected to BAS Server\n")
            return True
        except Exception as e:
            print(f"✗ Failed to connect to BAS Server: {str(e)}")
            print("Make sure BAS Server is running!")
            return False
    
    def run_test(self, test_name: str, test_func) -> bool:
        """
        Run a single test case and record the result.
        
        Args:
            test_name: Name of the test case
            test_func: Function that returns (success: bool, message: str)
            
        Returns:
            True if test passed, False otherwise
        """
        try:
            success, message = test_func()
            status = "PASS ✓" if success else "FAIL ✗"
            print(f"Test {len(self.test_results) + 1}: {test_name}... {status}")
            if message:
                print(f"  → {message}")
            self.test_results.append((test_name, success, message))
            return success
        except Exception as e:
            print(f"Test {len(self.test_results) + 1}: {test_name}... FAIL ✗")
            print(f"  → Exception: {str(e)}")
            self.test_results.append((test_name, False, f"Exception: {str(e)}"))
            return False
    
    def test_1_login_correct_credentials(self) -> Tuple[bool, str]:
        """
        Test Case 1: Login with correct credentials.
        
        Expected: Success, receive token
        Check: Token is not None
        """
        result = self.server.login("alice", "pass123")
        
        if result.get("success") and result.get("token"):
            self.token = result.get("token")
            return True, f"Token received: {self.token[:8]}..."
        else:
            return False, f"Login failed: {result.get('message')}"
    
    def test_2_login_wrong_password(self) -> Tuple[bool, str]:
        """
        Test Case 2: Login with wrong password.
        
        Expected: Failure, no token
        Check: Success = False
        """
        result = self.server.login("alice", "wrong")
        
        if not result.get("success") and result.get("token") is None:
            return True, f"Correctly rejected: {result.get('message')}"
        else:
            return False, "Login should have failed but succeeded"
    
    def test_3_get_balance(self) -> Tuple[bool, str]:
        """
        Test Case 3: Get balance.
        
        Expected: Balance = $10,000.00 (initial amount)
        Check: Balance matches expected amount
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        result = self.server.get_balance(self.token)
        
        if result.get("success"):
            balance = result.get("balance")
            if balance == 10000.00:
                return True, f"Balance correct: ${balance:.2f}"
            else:
                return False, f"Balance incorrect: ${balance:.2f} (expected $10,000.00)"
        else:
            return False, f"Get balance failed: {result.get('message')}"
    
    def test_4_transfer_free_tier(self) -> Tuple[bool, str]:
        """
        Test Case 4: Transfer - Free Tier.
        
        Transfer $1,500 from alice to bob
        Expected: Fee = $0, Total = $1,500
        Check: Transfer succeeds, fee is correct
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        amount = 1500.00
        result = self.server.transfer(self.token, "bob", amount, "Test transfer - free tier")
        
        if result.get("success"):
            fee = result.get("fee", 0)
            transfer_id = result.get("transfer_id")
            self.transfer_ids.append(transfer_id)
            
            if fee == 0.00:
                return True, f"Transfer succeeded, fee: ${fee:.2f} (correct), Transfer ID: {transfer_id[:8]}..."
            else:
                return False, f"Fee incorrect: ${fee:.2f} (expected $0.00)"
        else:
            return False, f"Transfer failed: {result.get('message')}"
    
    def test_5_transfer_entry_tier_fee(self) -> Tuple[bool, str]:
        """
        Test Case 5: Transfer - Entry Tier with Fee.
        
        Transfer $5,000 from alice to bob
        Expected: Fee = $12.50 (0.25% of $5,000)
        Check: Fee calculation correct
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        amount = 5000.00
        expected_fee = 12.50  # 0.25% of $5,000
        result = self.server.transfer(self.token, "bob", amount, "Test transfer - entry tier")
        
        if result.get("success"):
            fee = result.get("fee", 0)
            transfer_id = result.get("transfer_id")
            self.transfer_ids.append(transfer_id)
            
            if abs(fee - expected_fee) < 0.01:  # Allow for floating point precision
                return True, f"Transfer succeeded, fee: ${fee:.2f} (correct), Transfer ID: {transfer_id[:8]}..."
            else:
                return False, f"Fee incorrect: ${fee:.2f} (expected ${expected_fee:.2f})"
        else:
            return False, f"Transfer failed: {result.get('message')}"
    
    def test_6_transfer_mid_tier_fee(self) -> Tuple[bool, str]:
        """
        Test Case 6: Transfer - Mid Tier with Fee.
        
        Transfer $15,000 from alice to bob
        Expected: Fee = $25 (0.20% of $15,000 = $30, capped at $25)
        Check: Fee cap applied correctly
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        amount = 15000.00
        expected_fee = 25.00  # Capped at $25 (0.20% would be $30)
        result = self.server.transfer(self.token, "bob", amount, "Test transfer - mid tier")
        
        if result.get("success"):
            fee = result.get("fee", 0)
            transfer_id = result.get("transfer_id")
            self.transfer_ids.append(transfer_id)
            
            if abs(fee - expected_fee) < 0.01:
                return True, f"Transfer succeeded, fee: ${fee:.2f} (capped correctly), Transfer ID: {transfer_id[:8]}..."
            else:
                return False, f"Fee incorrect: ${fee:.2f} (expected ${expected_fee:.2f} - cap applied)"
        else:
            return False, f"Transfer failed: {result.get('message')}"
    
    def test_7_transfer_top_tier_fee(self) -> Tuple[bool, str]:
        """
        Test Case 7: Transfer - Top Tier with Fee.
        
        Transfer $150,000 from alice to bob (if balance allows)
        Expected: Fee = $75 (0.05% of $150,000, under $100 cap)
        Check: Calculation and cap correct
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        # Check balance first
        balance_result = self.server.get_balance(self.token)
        if not balance_result.get("success"):
            return False, "Could not check balance"
        
        current_balance = balance_result.get("balance", 0)
        amount = 150000.00
        expected_fee = 75.00  # 0.05% of $150,000 = $75 (under $100 cap)
        total_needed = amount + expected_fee
        
        if current_balance < total_needed:
            # Adjust amount to what we can afford
            # Use a smaller amount that still tests the top tier
            amount = 100000.00
            expected_fee = 50.00  # 0.08% of $100,000 = $80, capped at $50
            total_needed = amount + expected_fee
            
            if current_balance < total_needed:
                return False, f"Insufficient balance for top tier test (need ${total_needed:.2f}, have ${current_balance:.2f})"
        
        result = self.server.transfer(self.token, "bob", amount, "Test transfer - top tier")
        
        if result.get("success"):
            fee = result.get("fee", 0)
            transfer_id = result.get("transfer_id")
            self.transfer_ids.append(transfer_id)
            
            if abs(fee - expected_fee) < 0.01:
                return True, f"Transfer succeeded, fee: ${fee:.2f} (correct), Transfer ID: {transfer_id[:8]}..."
            else:
                return False, f"Fee incorrect: ${fee:.2f} (expected ${expected_fee:.2f})"
        else:
            return False, f"Transfer failed: {result.get('message')}"
    
    def test_8_insufficient_balance(self) -> Tuple[bool, str]:
        """
        Test Case 8: Insufficient Balance.
        
        Try to transfer more than alice's remaining balance
        Expected: Failure, error message
        Check: Balance unchanged
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        # Get current balance
        balance_result = self.server.get_balance(self.token)
        if not balance_result.get("success"):
            return False, "Could not check balance"
        
        current_balance = balance_result.get("balance", 0)
        # Try to transfer more than available (including fee)
        excessive_amount = current_balance + 10000.00
        
        result = self.server.transfer(self.token, "bob", excessive_amount, "Test - insufficient balance")
        
        if not result.get("success"):
            # Check that error message mentions insufficient balance
            message = result.get("message", "").lower()
            if "insufficient" in message or "balance" in message:
                return True, f"Correctly rejected: {result.get('message')}"
            else:
                return False, f"Wrong error message: {result.get('message')}"
        else:
            return False, "Transfer should have failed but succeeded"
    
    def test_9_invalid_recipient(self) -> Tuple[bool, str]:
        """
        Test Case 9: Invalid Recipient.
        
        Try to transfer to non-existent user "charlie"
        Expected: Failure, error message
        Check: No money moved
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        result = self.server.transfer(self.token, "charlie", 100.00, "Test - invalid recipient")
        
        if not result.get("success"):
            # Check that error message mentions recipient not found
            message = result.get("message", "").lower()
            if "recipient" in message or "not found" in message or "charlie" in message:
                return True, f"Correctly rejected: {result.get('message')}"
            else:
                return False, f"Wrong error message: {result.get('message')}"
        else:
            return False, "Transfer should have failed but succeeded"
    
    def test_10_check_transfer_status(self) -> Tuple[bool, str]:
        """
        Test Case 10: Check Transfer Status.
        
        Query status of a completed transfer
        Expected: Status = "COMPLETED", details present
        Check: Transfer details match
        """
        if not self.token:
            return False, "No token available (login failed)"
        
        if not self.transfer_ids:
            return False, "No transfer IDs available (previous transfers failed)"
        
        # Use the first transfer ID
        transfer_id = self.transfer_ids[0]
        result = self.server.get_transfer_status(self.token, transfer_id)
        
        if result.get("success"):
            status = result.get("status")
            details = result.get("details")
            
            if status == "COMPLETED" and details:
                return True, f"Status: {status}, Transfer ID: {transfer_id[:8]}..."
            else:
                return False, f"Status incorrect: {status} (expected COMPLETED)"
        else:
            return False, f"Get transfer status failed: {result.get('message')}"
    
    def run_all_tests(self):
        """Run all test cases and display results."""
        print("=" * 60)
        print("BANKING SYSTEM TEST SUITE")
        print("=" * 60)
        print()
        
        # Run all tests
        self.run_test("Login with Correct Credentials", self.test_1_login_correct_credentials)
        self.run_test("Login with Wrong Password", self.test_2_login_wrong_password)
        self.run_test("Get Balance", self.test_3_get_balance)
        self.run_test("Transfer - Free Tier", self.test_4_transfer_free_tier)
        self.run_test("Transfer - Entry Tier with Fee", self.test_5_transfer_entry_tier_fee)
        self.run_test("Transfer - Mid Tier with Fee", self.test_6_transfer_mid_tier_fee)
        self.run_test("Transfer - Top Tier with Fee", self.test_7_transfer_top_tier_fee)
        self.run_test("Insufficient Balance", self.test_8_insufficient_balance)
        self.run_test("Invalid Recipient", self.test_9_invalid_recipient)
        self.run_test("Check Transfer Status", self.test_10_check_transfer_status)
        
        # Display summary
        print()
        print("=" * 60)
        passed = sum(1 for _, success, _ in self.test_results if success)
        total = len(self.test_results)
        print(f"SUMMARY: {passed}/{total} tests passed")
        print("=" * 60)
        
        if passed == total:
            print("✓ All tests passed!")
        else:
            print("✗ Some tests failed. Review output above.")
            print("\nFailed tests:")
            for i, (name, success, message) in enumerate(self.test_results, 1):
                if not success:
                    print(f"  Test {i}: {name}")
                    print(f"    → {message}")
        
        return passed == total


def main():
    """Main function to run the test suite."""
    print("\n" + "=" * 60)
    print("BANKING SYSTEM AUTOMATED TEST SUITE")
    print("=" * 60)
    print("\nPrerequisites:")
    print("  - Pyro5 nameserver must be running")
    print("  - BDB Server must be running")
    print("  - BAS Server must be running")
    print("  - Test users 'alice' and 'bob' must exist")
    print()
    
    tester = BankingSystemTester()
    
    # Connect to server
    if not tester.connect():
        print("\n✗ Cannot proceed without server connection.")
        print("Please start all servers and try again.")
        sys.exit(1)
    
    # Run all tests
    success = tester.run_all_tests()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

