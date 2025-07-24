# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now
import requests
import json


class AccountingIntegration(Document):
	def validate(self):
		"""Validate accounting integration data"""
		self.validate_customer_permissions()
		self.validate_required_fields()
		
	def validate_customer_permissions(self):
		"""Ensure user can only access their own integration"""
		if frappe.session.user != "Administrator":
			user_email = frappe.session.user
			customer_email = frappe.db.get_value("SaaS Customer", self.customer, "email")
			
			if user_email != customer_email and not frappe.has_permission("Accounting Integration", "write"):
				frappe.throw("Access denied")
				
	def validate_required_fields(self):
		"""Validate required fields based on accounting system"""
		if self.accounting_system in ["QuickBooks", "Xero", "Sage"]:
			if not self.client_id or not self.client_secret:
				frappe.throw(f"{self.accounting_system} requires Client ID and Client Secret")
				
	def test_connection(self):
		"""Test connection to accounting system"""
		try:
			if self.accounting_system == "QuickBooks":
				return self.test_quickbooks_connection()
			elif self.accounting_system == "Xero":
				return self.test_xero_connection()
			elif self.accounting_system == "Manual Export":
				return {"success": True, "message": "Manual export configured"}
			else:
				return {"success": False, "error": "Unsupported accounting system"}
				
		except Exception as e:
			self.health_check_status = "Critical"
			self.last_health_check = now()
			self.error_message = str(e)
			self.save(ignore_permissions=True)
			
			return {"success": False, "error": str(e)}
			
	def test_quickbooks_connection(self):
		"""Test QuickBooks API connection"""
		if not self.access_token or not self.company_id:
			return {"success": False, "error": "Missing access token or company ID"}
			
		# Mock QuickBooks API test
		self.health_check_status = "Healthy"
		self.last_health_check = now()
		self.integration_status = "Connected"
		self.save(ignore_permissions=True)
		
		return {"success": True, "message": "QuickBooks connection successful"}
		
	def test_xero_connection(self):
		"""Test Xero API connection"""
		if not self.access_token:
			return {"success": False, "error": "Missing access token"}
			
		# Mock Xero API test
		self.health_check_status = "Healthy"
		self.last_health_check = now()
		self.integration_status = "Connected"
		self.save(ignore_permissions=True)
		
		return {"success": True, "message": "Xero connection successful"}
		
	def export_invoice_data(self, invoice_data):
		"""Export invoice data to accounting system"""
		try:
			if self.accounting_system == "QuickBooks":
				result = self.export_to_quickbooks(invoice_data)
			elif self.accounting_system == "Xero":
				result = self.export_to_xero(invoice_data)
			elif self.accounting_system == "Manual Export":
				result = self.export_manual(invoice_data)
			else:
				result = {"success": False, "error": "Unsupported accounting system"}
				
			# Update export statistics
			self.total_exports = (self.total_exports or 0) + 1
			
			if result.get("success"):
				self.successful_exports = (self.successful_exports or 0) + 1
				self.last_successful_sync = now()
			else:
				self.failed_exports = (self.failed_exports or 0) + 1
				self.sync_errors = result.get("error", "Unknown error")
				
			self.last_sync = now()
			self.save(ignore_permissions=True)
			
			return result
			
		except Exception as e:
			frappe.log_error(f"Export error: {str(e)}")
			return {"success": False, "error": str(e)}
			
	def export_to_quickbooks(self, invoice_data):
		"""Export to QuickBooks"""
		# Mock QuickBooks export
		return {
			"success": True, 
			"external_id": f"QB-{frappe.generate_hash(length=8)}",
			"message": "Exported to QuickBooks successfully"
		}
		
	def export_to_xero(self, invoice_data):
		"""Export to Xero"""
		# Mock Xero export
		return {
			"success": True,
			"external_id": f"XR-{frappe.generate_hash(length=8)}",
			"message": "Exported to Xero successfully"
		}
		
	def export_manual(self, invoice_data):
		"""Generate manual export file"""
		# For manual export, generate CSV/JSON file
		return {
			"success": True,
			"export_format": self.export_format or "JSON",
			"message": "Manual export data prepared"
		}
		
	def refresh_access_token(self):
		"""Refresh OAuth access token"""
		try:
			if not self.refresh_token:
				return {"success": False, "error": "No refresh token available"}
				
			# Mock token refresh
			self.access_token = f"new_token_{frappe.generate_hash(length=16)}"
			self.save(ignore_permissions=True)
			
			return {"success": True, "message": "Access token refreshed"}
			
		except Exception as e:
			return {"success": False, "error": str(e)}


@frappe.whitelist()
def test_accounting_connection(integration_name):
	"""Test accounting system connection"""
	integration = frappe.get_doc("Accounting Integration", integration_name)
	
	# Check permissions
	customer = frappe.get_doc("SaaS Customer", integration.customer)
	if frappe.session.user != customer.email and not frappe.has_permission("Accounting Integration", "write"):
		frappe.throw("Access denied")
		
	return integration.test_connection()


@frappe.whitelist()
def get_customer_accounting_integration(customer_name=None):
	"""Get customer's accounting integration"""
	if not customer_name:
		customer_name = frappe.db.get_value("SaaS Customer", 
			{"email": frappe.session.user}, "name")
			
	if not customer_name:
		return None
		
	integration = frappe.db.get_value("Accounting Integration", 
		{"customer": customer_name}, "name")
		
	if integration:
		return frappe.get_doc("Accounting Integration", integration)
	
	return None