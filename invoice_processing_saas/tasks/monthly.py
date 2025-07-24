# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def archive_old_data():
	"""
	Archive old data (monthly)
	"""
	try:
		frappe.logger().info("Archiving old data")
		# Add your data archiving logic here
	except Exception as e:
		frappe.log_error(f"Error in archive_old_data: {str(e)}", "Monthly Tasks")


def subscription_billing():
	"""
	Process monthly subscription billing
	"""
	try:
		frappe.logger().info("Processing subscription billing")
		# Add your billing logic here
	except Exception as e:
		frappe.log_error(f"Error in subscription_billing: {str(e)}", "Monthly Tasks")
