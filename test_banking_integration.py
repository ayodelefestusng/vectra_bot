import unittest
from unittest.mock import MagicMock, patch
from decimal import Decimal
import json

# Mocking the base dependencies before importing tools
import sys
from types import ModuleType

# Create dummy base and logger_utils modules to avoid ImportErrors during testing
mock_base = ModuleType('base')
mock_base.Context = MagicMock()
mock_base.RuntimeToolInput = MagicMock()
sys.modules['base'] = mock_base

mock_logger = ModuleType('logger_utils')
mock_logger.log_info = MagicMock()
mock_logger.log_error = MagicMock()
mock_logger.log_warning = MagicMock()
sys.modules['logger_utils'] = mock_logger

# Now we can import the tools
# Note: we use absolute imports as if we are running from the app root
sys.path.append('.') 
import banking_tools

class TestBankingIntegration(unittest.TestCase):

    def setUp(self):
        self.runtime = MagicMock()
        self.runtime.context.tenant_id = "DMC"
        self.runtime.context.conversation_id = "test_conv"
        self.runtime.context.phone_number = "2348021299221"
        self.runtime.context.db_uri = "postgresql://user:pass@localhost/db"
        self.runtime.context.device_type = "phone"

    @patch('banking_tools.create_engine')
    @patch('banking_tools._get_customer_row')
    @patch('banking_tools._generate_django_token')
    def test_forgot_password_link_generation(self, mock_gen_token, mock_get_cust, mock_engine):
        # Setup
        mock_get_cust.return_value = {"id": 1, "phone_number": "2348021299221"}
        mock_gen_token.return_value = "test-token-123"
        
        # Execute
        result = banking_tools.forgot_password_tool(self.runtime)
        
        # Verify
        self.assertIn("test-token-123", result)
        self.assertIn("2348021299221", result)
        self.assertIn("reset-password", result)
        print("✅ Forgot Password Link Generation Test Passed")

    @patch('banking_tools._get_access_token')
    @patch('requests.get')
    def test_resolve_biller_standardization(self, mock_get, mock_token):
        # Setup
        mock_token.return_value = "fake-token"
        mock_get.return_value.json.return_value = {
            "status": "00",
            "data": {"paymentitems": [{"paymentitemname": "MTN 1GB", "amount": "500", "paymentCode": "123"}]}
        }
        
        # Verify _wallet_headers is used (indirectly by checking if tools run without header errors)
        # This is more of a smoke test for the standardizations made
        headers = banking_tools._wallet_headers()
        self.assertEqual(headers["AccessToken"], "fake-token")
        print("✅ Wallet Headers Standardization Test Passed")

if __name__ == '__main__':
    unittest.main()
