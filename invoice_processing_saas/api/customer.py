# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def after_customer_insert(doc, method):
	"""
	Called after SaaS Customer document is inserted
	"""
	try:
		# Log customer creation
		frappe.logger().info(f"New SaaS Customer created: {doc.customer_name} ({doc.email})")
		
		# You can add additional logic here like:
		# - Send notifications to admin
		# - Create initial integrations
		# - Setup default configurations
		
	except Exception as e:
		frappe.log_error(f"Error in after_customer_insert: {str(e)}", "Customer API")


def on_customer_update(doc, method):
	"""
	Called when SaaS Customer document is updated
	"""
	try:
		# Handle subscription plan changes
		if doc.has_value_changed("subscription_plan"):
			frappe.logger().info(f"Customer {doc.customer_name} changed plan to {doc.subscription_plan}")
			
		# Handle subscription status changes
		if doc.has_value_changed("subscription_status"):
			frappe.logger().info(f"Customer {doc.customer_name} status changed to {doc.subscription_status}")
			
			# Disable integrations if subscription becomes inactive
			if doc.subscription_status not in ["Active", "Trial"]:
				_disable_customer_integrations(doc.name)
		
	except Exception as e:
		frappe.log_error(f"Error in on_customer_update: {str(e)}", "Customer API")


def _disable_customer_integrations(customer_name):
	"""
	Disable all integrations for inactive customers
	"""
	try:
		# Disable Drive Integrations
		drive_integrations = frappe.get_all("Drive Integration", 
			filters={"customer": customer_name, "integration_status": "Active"})
		
		for integration in drive_integrations:
			doc = frappe.get_doc("Drive Integration", integration.name)
			doc.integration_status = "Suspended"
			doc.save(ignore_permissions=True)
			
		# Disable Accounting Integrations  
		accounting_integrations = frappe.get_all("Accounting Integration",
			filters={"customer": customer_name, "integration_status": "Connected"})
			
		for integration in accounting_integrations:
			doc = frappe.get_doc("Accounting Integration", integration.name)
			doc.integration_status = "Suspended"
			doc.save(ignore_permissions=True)
			
		frappe.logger().info(f"Disabled integrations for customer: {customer_name}")
		
	except Exception as e:
		frappe.log_error(f"Error disabling integrations for {customer_name}: {str(e)}", "Customer API")


@frappe.whitelist()
def get_customer_stats(customer_name):
	"""
	API endpoint to get customer statistics
	"""
	try:
		customer = frappe.get_doc("SaaS Customer", customer_name)
		
		# Check permissions
		if frappe.session.user != customer.email and not frappe.has_permission("SaaS Customer", "read", customer_name):
			frappe.throw("Not permitted")
			
		return {
			"current_usage": customer.current_usage or 0,
			"usage_limit": customer.usage_limit or 0,
			"total_processed": customer.total_processed or 0,
			"subscription_status": customer.subscription_status,
			"subscription_plan": customer.subscription_plan,
			"trial_end_date": customer.trial_end_date
		}
		
	except Exception as e:
		frappe.log_error(f"Error getting customer stats: {str(e)}", "Customer API")
		frappe.throw("Failed to get customer statistics")


@frappe.whitelist()
def update_customer_profile(customer_name, **kwargs):
	"""
	API endpoint to update customer profile
	"""
	try:
		customer = frappe.get_doc("SaaS Customer", customer_name)
		
		# Check permissions
		if frappe.session.user != customer.email and not frappe.has_permission("SaaS Customer", "write", customer_name):
			frappe.throw("Not permitted")
			
		# Update allowed fields
		allowed_fields = ["customer_name", "phone", "company"]
		
		for field, value in kwargs.items():
			if field in allowed_fields and value is not None:
				setattr(customer, field, value)
		
		customer.save(ignore_permissions=True)
		
		return {"message": "Profile updated successfully"}
		
	except Exception as e:
		frappe.log_error(f"Error updating customer profile: {str(e)}", "Customer API")
		frappe.throw("Failed to update profile")
