# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import now


def after_job_insert(doc, method):
	"""
	Called after Processing Job document is inserted
	"""
	try:
		# Log job creation
		frappe.logger().info(f"New processing job created: {doc.name} for customer {doc.customer}")
		
		# Update customer's last activity
		if doc.customer:
			customer = frappe.get_doc("SaaS Customer", doc.customer)
			customer.last_activity = now()
			customer.save(ignore_permissions=True)
		
	except Exception as e:
		frappe.log_error(f"Error in after_job_insert: {str(e)}", "Processing API")


def on_job_update(doc, method):
	"""
	Called when Processing Job document is updated
	"""
	try:
		# Handle status changes
		if doc.has_value_changed("processing_status"):
			frappe.logger().info(f"Job {doc.name} status changed to {doc.processing_status}")
			
			# If job completed successfully, increment customer usage
			if doc.processing_status == "Completed" and doc.customer:
				customer = frappe.get_doc("SaaS Customer", doc.customer)
				customer.increment_usage()
				
			# Send notification for failed jobs
			elif doc.processing_status == "Failed":
				_notify_job_failure(doc)
		
	except Exception as e:
		frappe.log_error(f"Error in on_job_update: {str(e)}", "Processing API")


def _notify_job_failure(job_doc):
	"""
	Send notification for failed jobs
	"""
	try:
		if job_doc.customer:
			customer = frappe.get_doc("SaaS Customer", job_doc.customer)
			
			frappe.sendmail(
				recipients=[customer.email],
				subject="Processing Job Failed",
				template="job_failure_notification",
				args={
					"customer_name": customer.customer_name,
					"job_name": job_doc.name,
					"file_name": job_doc.file_name,
					"error_message": job_doc.error_message or "Unknown error",
					"dashboard_url": f"{frappe.utils.get_url()}/dashboard"
				}
			)
			
	except Exception as e:
		frappe.log_error(f"Error sending job failure notification: {str(e)}", "Processing API")


@frappe.whitelist()
def create_job(file_name, file_url, customer_id=None, extraction_engine="GPT-4"):
	"""
	API endpoint for n8n to create processing jobs
	"""
	try:
		# Get customer by API key if not provided
		if not customer_id:
			api_key = frappe.get_request_header("X-API-Key")
			if not api_key:
				frappe.throw("API key required")
				
			customer_id = frappe.db.get_value("SaaS Customer", {"api_key": api_key}, "name")
			if not customer_id:
				frappe.throw("Invalid API key")
		
		# Check customer quota
		customer = frappe.get_doc("SaaS Customer", customer_id)
		if not customer.check_usage_quota():
			return {"error": "Quota exceeded"}
		
		# Create processing job
		job = frappe.get_doc({
			"doctype": "Processing Job",
			"customer": customer_id,
			"file_name": file_name,
			"file_url": file_url,
			"extraction_engine": extraction_engine,
			"processing_status": "Pending",
			"created_via": "API"
		})
		job.insert(ignore_permissions=True)
		
		return {
			"job_id": job.name,
			"status": "created",
			"message": "Processing job created successfully"
		}
		
	except Exception as e:
		frappe.log_error(f"Error creating processing job: {str(e)}", "Processing API")
		return {"error": str(e)}


@frappe.whitelist()
def store_result(job_id, extracted_data, processing_time=None):
	"""
	API endpoint for n8n to store processing results
	"""
	try:
		job = frappe.get_doc("Processing Job", job_id)
		
		# Update job with results
		job.extracted_data = frappe.as_json(extracted_data) if extracted_data else "{}"
		job.processing_status = "Completed"
		job.completed_at = now()
		
		if processing_time:
			job.processing_time = processing_time
			
		job.save(ignore_permissions=True)
		
		return {
			"status": "success",
			"message": "Results stored successfully"
		}
		
	except Exception as e:
		frappe.log_error(f"Error storing processing result: {str(e)}", "Processing API")
		return {"error": str(e)}


@frappe.whitelist()
def update_job_status(job_id, status, error_message=None):
	"""
	API endpoint to update job status
	"""
	try:
		job = frappe.get_doc("Processing Job", job_id)
		
		job.processing_status = status
		
		if error_message:
			job.error_message = error_message
			
		if status in ["Completed", "Failed"]:
			job.completed_at = now()
			
		job.save(ignore_permissions=True)
		
		return {
			"status": "success",
			"message": f"Job status updated to {status}"
		}
		
	except Exception as e:
		frappe.log_error(f"Error updating job status: {str(e)}", "Processing API")
		return {"error": str(e)}


@frappe.whitelist()
def get_job_status(job_id):
	"""
	API endpoint to get job status
	"""
	try:
		job = frappe.get_doc("Processing Job", job_id)
		
		return {
			"job_id": job.name,
			"status": job.processing_status,
			"file_name": job.file_name,
			"created_at": job.creation,
			"completed_at": job.completed_at,
			"processing_time": job.processing_time,
			"extracted_data": frappe.parse_json(job.extracted_data) if job.extracted_data else {}
		}
		
	except Exception as e:
		frappe.log_error(f"Error getting job status: {str(e)}", "Processing API")
		return {"error": str(e)}
