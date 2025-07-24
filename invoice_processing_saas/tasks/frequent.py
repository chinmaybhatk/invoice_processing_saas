# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def check_integration_health():
	"""
	Check health of all integrations (every 15 minutes)
	"""
	try:
		frappe.logger().info("Checking integration health")
		# Add your integration health check logic here
	except Exception as e:
		frappe.log_error(f"Error in check_integration_health: {str(e)}", "Frequent Tasks")


def process_pending_jobs():
	"""
	Process any pending jobs (every 15 minutes)
	"""
	try:
		frappe.logger().info("Processing pending jobs")
		# Add your pending job processing logic here
	except Exception as e:
		frappe.log_error(f"Error in process_pending_jobs: {str(e)}", "Frequent Tasks")
