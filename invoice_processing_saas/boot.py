# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def boot_session(bootinfo):
	"""
	Called when user session boots
	Add custom data to bootinfo
	"""
	try:
		if frappe.session.user and frappe.session.user != "Guest":
			# Check if user is a SaaS customer
			customer = frappe.db.get_value("SaaS Customer", 
				{"email": frappe.session.user}, 
				["name", "customer_name", "subscription_status", "subscription_plan"])
				
			if customer:
				bootinfo.saas_customer = {
					"name": customer[0],
					"customer_name": customer[1], 
					"subscription_status": customer[2],
					"subscription_plan": customer[3],
					"is_saas_customer": True
				}
			else:
				bootinfo.saas_customer = {
					"is_saas_customer": False
				}
				
		# Add app-specific settings
		bootinfo.invoice_processing_settings = {
			"app_name": "Invoice Processing SaaS",
			"version": "1.0.0",
			"support_email": "support@yourcompany.com"
		}
		
	except Exception as e:
		frappe.log_error(f"Error in boot_session: {str(e)}", "Boot Session")
