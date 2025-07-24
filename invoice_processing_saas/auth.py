# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def validate_auth_via_api_keys(api_key=None):
	"""
	Custom authentication via API keys
	"""
	try:
		if not api_key:
			api_key = frappe.get_request_header("X-API-Key")
			
		if not api_key:
			return False
			
		# Check if API key exists and is valid
		customer = frappe.db.get_value("SaaS Customer", 
			{"api_key": api_key, "subscription_status": ["in", ["Active", "Trial"]]}, 
			["name", "email"])
			
		if customer:
			# Set user session for API requests
			frappe.set_user(customer[1])
			return True
			
		return False
		
	except Exception as e:
		frappe.log_error(f"Error in API key authentication: {str(e)}", "Auth")
		return False


def get_current_user_customer():
	"""
	Get the current user's customer record
	"""
	try:
		if frappe.session.user and frappe.session.user != "Guest":
			customer = frappe.db.get_value("SaaS Customer", 
				{"email": frappe.session.user}, "name")
			return customer
		return None
	except Exception as e:
		frappe.log_error(f"Error getting current user customer: {str(e)}", "Auth")
		return None
