# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe


def on_usage_update(doc, method):
	"""
	Called when Usage Tracking document is updated
	"""
	try:
		# Log usage tracking update
		frappe.logger().info(f"Usage updated for customer {doc.customer}: {doc.current_usage}/{doc.usage_limit}")
		
		# Send alerts if approaching limits
		if doc.current_usage and doc.usage_limit:
			usage_percentage = (doc.current_usage / doc.usage_limit) * 100
			
			# Send warning at 80%, 90%, and 100%
			if usage_percentage >= 80 and not doc.alert_80_sent:
				_send_usage_alert(doc, 80)
				doc.alert_80_sent = 1
				
			elif usage_percentage >= 90 and not doc.alert_90_sent:
				_send_usage_alert(doc, 90)
				doc.alert_90_sent = 1
				
			elif usage_percentage >= 100 and not doc.alert_100_sent:
				_send_usage_alert(doc, 100)
				doc.alert_100_sent = 1
		
	except Exception as e:
		frappe.log_error(f"Error in on_usage_update: {str(e)}", "Usage API")


def _send_usage_alert(usage_doc, percentage):
	"""
	Send usage alert email
	"""
	try:
		customer = frappe.get_doc("SaaS Customer", usage_doc.customer)
		
		subject = f"Usage Alert: {percentage}% of monthly quota used"
		if percentage >= 100:
			subject = "Monthly Quota Exceeded - Action Required"
			
		frappe.sendmail(
			recipients=[customer.email],
			subject=subject,
			template="usage_alert",
			args={
				"customer_name": customer.customer_name,
				"current_usage": usage_doc.current_usage,
				"usage_limit": usage_doc.usage_limit,
				"percentage": percentage,
				"upgrade_url": f"{frappe.utils.get_url()}/billing"
			}
		)
		
		frappe.logger().info(f"Sent {percentage}% usage alert to {customer.email}")
		
	except Exception as e:
		frappe.log_error(f"Error sending usage alert: {str(e)}", "Usage API")


@frappe.whitelist()
def get_usage_stats(customer_name, period="current_month"):
	"""
	API endpoint to get usage statistics
	"""
	try:
		customer = frappe.get_doc("SaaS Customer", customer_name)
		
		# Check permissions
		if frappe.session.user != customer.email and not frappe.has_permission("SaaS Customer", "read", customer_name):
			frappe.throw("Not permitted")
		
		if period == "current_month":
			return {
				"current_usage": customer.current_usage or 0,
				"usage_limit": customer.usage_limit or 0,
				"usage_percentage": (customer.current_usage / customer.usage_limit * 100) if customer.usage_limit else 0,
				"remaining_quota": max(0, (customer.usage_limit or 0) - (customer.current_usage or 0))
			}
		
		# Add more period options as needed
		
	except Exception as e:
		frappe.log_error(f"Error getting usage stats: {str(e)}", "Usage API")
		frappe.throw("Failed to get usage statistics")


@frappe.whitelist()
def reset_usage_alerts(customer_name):
	"""
	Reset usage alert flags (called monthly)
	"""
	try:
		usage_tracking = frappe.get_all("Usage Tracking", 
			filters={"customer": customer_name}, 
			limit=1)
			
		if usage_tracking:
			doc = frappe.get_doc("Usage Tracking", usage_tracking[0].name)
			doc.alert_80_sent = 0
			doc.alert_90_sent = 0  
			doc.alert_100_sent = 0
			doc.save(ignore_permissions=True)
			
		return {"message": "Usage alerts reset successfully"}
		
	except Exception as e:
		frappe.log_error(f"Error resetting usage alerts: {str(e)}", "Usage API")
		return {"error": str(e)}
