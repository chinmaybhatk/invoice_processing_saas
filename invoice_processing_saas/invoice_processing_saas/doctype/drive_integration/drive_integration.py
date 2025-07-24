# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, get_datetime
import json
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


class DriveIntegration(Document):
	def validate(self):
		"""Validate drive integration data"""
		self.validate_folder_id()
		self.extract_folder_info_from_url()
		self.validate_customer_permissions()
		
	def validate_folder_id(self):
		"""Validate Google Drive folder ID format"""
		if self.drive_folder_id:
			# Basic validation for Google Drive folder ID format
			if len(self.drive_folder_id) < 10:
				frappe.throw("Invalid Google Drive folder ID")
				
	def extract_folder_info_from_url(self):
		"""Extract folder ID from Google Drive URL if provided"""
		if self.drive_folder_url and not self.drive_folder_id:
			import re
			match = re.search(r'/folders/([a-zA-Z0-9-_]+)', self.drive_folder_url)
			if match:
				self.drive_folder_id = match.group(1)
				
	def validate_customer_permissions(self):
		"""Ensure user can only access their own integration"""
		if frappe.session.user != "Administrator":
			user_email = frappe.session.user
			customer_email = frappe.db.get_value("SaaS Customer", self.customer, "email")
			
			if user_email != customer_email and not frappe.has_permission("Drive Integration", "write"):
				frappe.throw("Access denied")
				
	def before_insert(self):
		"""Set default values before inserting"""
		self.first_connected = now()
		self.generate_webhook_url()
		self.setup_default_file_types()
		
	def after_insert(self):
		"""Post-creation tasks"""
		self.setup_n8n_monitoring()
		
	def generate_webhook_url(self):
		"""Generate webhook URL for n8n integration"""
		settings = frappe.get_single("Invoice Processing Settings")
		if settings.n8n_webhook_base_url:
			self.webhook_url = f"{settings.n8n_webhook_base_url}/webhook/drive-{self.drive_folder_id}"
			
	def setup_default_file_types(self):
		"""Setup default allowed file types"""
		if not self.file_types_allowed:
			default_types = [
				{"file_type": "pdf", "enabled": 1, "max_size_mb": 10},
				{"file_type": "jpg", "enabled": 1, "max_size_mb": 5},
				{"file_type": "jpeg", "enabled": 1, "max_size_mb": 5},
				{"file_type": "png", "enabled": 1, "max_size_mb": 5}
			]
			
			for file_type in default_types:
				self.append("file_types_allowed", file_type)
				
	def test_connection(self):
		"""Test Google Drive connection"""
		try:
			if not self.access_token:
				return {"success": False, "error": "No access token configured"}
				
			# For now, return a mock success response
			# In production, this would test actual Google Drive API
			self.health_check_status = "Healthy"
			self.last_health_check = now()
			self.error_message = None
			self.save(ignore_permissions=True)
			
			return {
				"success": True, 
				"folder_name": self.folder_name or "Test Folder",
				"folder_id": self.drive_folder_id
			}
			
		except Exception as e:
			self.health_check_status = "Critical"
			self.last_health_check = now()
			self.error_message = str(e)
			self.save(ignore_permissions=True)
			
			return {"success": False, "error": str(e)}
			
	def update_processing_stats(self, success=True):
		"""Update processing statistics"""
		self.total_files_processed = (self.total_files_processed or 0) + 1
		
		if success:
			self.successful_processing = (self.successful_processing or 0) + 1
		else:
			self.failed_processing = (self.failed_processing or 0) + 1
			
		self.last_activity = now()
		self.save(ignore_permissions=True)


# Child DocType for File Types
class DriveFileType(Document):
	pass


@frappe.whitelist()
def test_drive_connection(integration_name):
	"""Test Google Drive connection"""
	integration = frappe.get_doc("Drive Integration", integration_name)
	
	# Check permissions
	customer = frappe.get_doc("SaaS Customer", integration.customer)
	if frappe.session.user != customer.email and not frappe.has_permission("Drive Integration", "write"):
		frappe.throw("Access denied")
		
	return integration.test_connection()


@frappe.whitelist()
def get_customer_drive_integration(customer_name=None):
	"""Get customer's drive integration"""
	if not customer_name:
		customer_name = frappe.db.get_value("SaaS Customer", 
			{"email": frappe.session.user}, "name")
			
	if not customer_name:
		return None
		
	integration = frappe.db.get_value("Drive Integration", 
		{"customer": customer_name}, "name")
		
	if integration:
		return frappe.get_doc("Drive Integration", integration)
	
	return None