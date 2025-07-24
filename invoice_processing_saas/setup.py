# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint


def after_install():
	"""
	Called after app installation
	"""
	try:
		# Create custom fields
		create_app_custom_fields()
		
		# Create default subscription plans
		create_default_subscription_plans()
		
		# Setup default settings
		setup_default_settings()
		
		# Create customer role if it doesn't exist
		create_customer_role()
		
		frappe.db.commit()
		print("Invoice Processing SaaS: Installation completed successfully")
		
	except Exception as e:
		frappe.log_error(f"Error during app installation: {str(e)}", "Invoice Processing SaaS Setup")
		print(f"Warning: Some setup steps failed: {str(e)}")


def after_app_install():
	"""
	Called after any app installation (not just this app)
	"""
	pass


def create_app_custom_fields():
	"""
	Create custom fields for existing doctypes
	"""
	custom_fields = {
		"User": [
			{
				"fieldname": "is_saas_customer",
				"label": "Is SaaS Customer",
				"fieldtype": "Check",
				"insert_after": "user_type",
				"default": "0"
			},
			{
				"fieldname": "saas_customer_id",
				"label": "SaaS Customer ID",
				"fieldtype": "Link",
				"options": "SaaS Customer",
				"insert_after": "is_saas_customer",
				"depends_on": "is_saas_customer"
			}
		],
		"Customer": [
			{
				"fieldname": "is_saas_customer",
				"label": "Is SaaS Customer",
				"fieldtype": "Check",
				"insert_after": "customer_type",
				"default": "0"
			},
			{
				"fieldname": "saas_customer_link",
				"label": "SaaS Customer",
				"fieldtype": "Link",
				"options": "SaaS Customer",
				"insert_after": "is_saas_customer",
				"depends_on": "is_saas_customer"
			}
		]
	}
	
	try:
		create_custom_fields(custom_fields, update=True)
		print("Custom fields created successfully")
	except Exception as e:
		frappe.log_error(f"Error creating custom fields: {str(e)}", "Setup Custom Fields")


def create_default_subscription_plans():
	"""
	Create default subscription plans
	"""
	plans = [
		{
			"plan_name": "Starter Plan",
			"monthly_rate": 29.0,
			"processing_limit": 100,
			"trial_days": 14,
			"description": "Perfect for small businesses getting started with invoice automation",
			"features": ["100 invoices per month", "Basic AI extraction", "Email support", "Drive integration"]
		},
		{
			"plan_name": "Professional Plan", 
			"monthly_rate": 79.0,
			"processing_limit": 500,
			"trial_days": 14,
			"description": "Ideal for growing businesses with higher processing needs",
			"features": ["500 invoices per month", "Advanced AI extraction", "Priority support", "All integrations", "Custom fields"]
		},
		{
			"plan_name": "Enterprise Plan",
			"monthly_rate": 199.0,
			"processing_limit": 2000,
			"trial_days": 30,
			"description": "For large organizations with high-volume processing requirements",
			"features": ["2000 invoices per month", "Premium AI extraction", "24/7 support", "Custom integrations", "Advanced analytics"]
		}
	]
	
	for plan_data in plans:
		if not frappe.db.exists("Subscription Plan", plan_data["plan_name"]):
			try:
				plan = frappe.get_doc({
					"doctype": "Subscription Plan",
					"plan_name": plan_data["plan_name"],
					"monthly_rate": plan_data["monthly_rate"],
					"processing_limit": plan_data["processing_limit"],
					"trial_days": plan_data["trial_days"],
					"description": plan_data["description"],
					"is_active": 1,
					"features": "\n".join(plan_data["features"])
				})
				plan.insert(ignore_permissions=True)
				print(f"Created subscription plan: {plan_data['plan_name']}")
			except Exception as e:
				frappe.log_error(f"Error creating plan {plan_data['plan_name']}: {str(e)}", "Setup Subscription Plans")


def setup_default_settings():
	"""
	Setup default app settings
	"""
	try:
		# Create Invoice Processing Settings if it doesn't exist
		if not frappe.db.exists("Invoice Processing Settings", "Invoice Processing Settings"):
			settings = frappe.get_doc({
				"doctype": "Invoice Processing Settings",
				"name": "Invoice Processing Settings",
				"default_extraction_engine": "OpenAI GPT-4",
				"max_file_size_mb": 10,
				"supported_file_types": "pdf,jpg,jpeg,png",
				"enable_webhook_notifications": 1,
				"webhook_timeout_seconds": 30,
				"default_trial_days": 14,
				"enable_usage_alerts": 1,
				"usage_alert_threshold": 80
			})
			settings.insert(ignore_permissions=True)
			print("Created default Invoice Processing Settings")
	except Exception as e:
		frappe.log_error(f"Error creating settings: {str(e)}", "Setup Default Settings")


def create_customer_role():
	"""
	Create Customer role if it doesn't exist
	"""
	try:
		if not frappe.db.exists("Role", "Customer"):
			role = frappe.get_doc({
				"doctype": "Role",
				"role_name": "Customer",
				"desk_access": 0,
				"is_custom": 1
			})
			role.insert(ignore_permissions=True)
			print("Created Customer role")
			
		# Add permissions for Customer role
		add_customer_permissions()
		
	except Exception as e:
		frappe.log_error(f"Error creating Customer role: {str(e)}", "Setup Customer Role")


def add_customer_permissions():
	"""
	Add permissions for Customer role
	"""
	permissions = [
		{
			"doctype": "DocPerm",
			"parent": "SaaS Customer",
			"parenttype": "DocType",
			"role": "Customer",
			"read": 1,
			"write": 1,
			"if_owner": 1
		},
		{
			"doctype": "DocPerm", 
			"parent": "Processing Job",
			"parenttype": "DocType",
			"role": "Customer",
			"read": 1,
			"if_owner": 1
		},
		{
			"doctype": "DocPerm",
			"parent": "Drive Integration",
			"parenttype": "DocType", 
			"role": "Customer",
			"read": 1,
			"write": 1,
			"if_owner": 1
		},
		{
			"doctype": "DocPerm",
			"parent": "Accounting Integration",
			"parenttype": "DocType",
			"role": "Customer", 
			"read": 1,
			"write": 1,
			"if_owner": 1
		}
	]
	
	try:
		for perm in permissions:
			if not frappe.db.exists("DocPerm", {
				"parent": perm["parent"],
				"role": perm["role"],
				"parenttype": "DocType"
			}):
				doc = frappe.get_doc(perm)
				doc.insert(ignore_permissions=True)
				print(f"Added {perm['role']} permission for {perm['parent']}")
	except Exception as e:
		frappe.log_error(f"Error adding permissions: {str(e)}", "Setup Permissions")


def before_uninstall():
	"""
	Called before app uninstallation
	"""
	try:
		# Cleanup tasks before uninstalling
		print("Cleaning up Invoice Processing SaaS data...")
		
		# You can add cleanup tasks here if needed
		# Be careful not to delete important data
		
	except Exception as e:
		frappe.log_error(f"Error during app uninstallation: {str(e)}", "Invoice Processing SaaS Uninstall")
