# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from frappe.utils import nowdate, now


@frappe.whitelist(allow_guest=True, methods=["POST"])
def lookup_user_by_folder():
	"""
	n8n API endpoint to lookup user by Google Drive folder ID
	Used by n8n workflow to validate user and get configuration
	"""
	try:
		# Get request data
		data = frappe.local.form_dict
		folder_id = data.get("folder_id")
		
		if not folder_id:
			return {"user_found": False, "error": "folder_id is required"}
			
		# Find customer by drive folder ID
		drive_integration = frappe.db.get_value("Drive Integration", 
			{"drive_folder_id": folder_id}, 
			["customer", "integration_status", "setup_completed"])
			
		if not drive_integration:
			return {"user_found": False, "error": "No customer found for this folder"}
			
		customer_name = drive_integration[0]
		integration_status = drive_integration[1]
		setup_completed = drive_integration[2]
		
		# Get customer details
		customer = frappe.get_doc("SaaS Customer", customer_name)
		
		# Check if customer is active
		if customer.subscription_status not in ["Active", "Trial"]:
			return {
				"user_found": False, 
				"error": f"Customer subscription is {customer.subscription_status}"
			}
			
		# Check if integration is ready
		if integration_status != "Active" or not setup_completed:
			return {
				"user_found": False,
				"error": "Drive integration not properly configured"
			}
			
		# Get accounting integration
		accounting_integration = frappe.db.get_value("Accounting Integration",
			{"customer": customer_name}, 
			["accounting_system", "integration_status"])
			
		# Get usage info
		usage_remaining = max(0, customer.usage_limit - customer.current_usage) if customer.usage_limit else 0
		
		# Determine preferred engine based on customer plan and complexity
		preferred_engine = "azure"  # Default to Azure for efficiency
		
		# Check if customer has premium plan (may prefer OpenAI)
		if customer.subscription_plan:
			plan = frappe.get_doc("Subscription Plan", customer.subscription_plan)
			if plan.plan_code in ["pro", "enterprise"]:
				preferred_engine = "openai"
				
		return {
			"user_found": True,
			"customer_id": customer.name,
			"user_config": {
				"customer_name": customer.customer_name,
				"email": customer.email,
				"subscription_status": customer.subscription_status,
				"subscription_plan": customer.subscription_plan,
				"current_usage": customer.current_usage,
				"usage_limit": customer.usage_limit,
				"usage_remaining": usage_remaining,
				"overage_allowed": customer.overage_allowed,
				"preferred_engine": preferred_engine,
				"accounting_system": accounting_integration[0] if accounting_integration else None,
				"accounting_status": accounting_integration[1] if accounting_integration else "Not Connected",
				"api_key": customer.api_key,
				"webhook_secret": customer.webhook_secret
			}
		}
		
	except Exception as e:
		frappe.log_error(f"Error in lookup_user_by_folder: {str(e)}")
		return {"user_found": False, "error": "Internal server error"}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def create_processing_job():
	"""
	n8n API endpoint to create a new processing job
	Called when n8n starts processing a file
	"""
	try:
		data = frappe.local.form_dict
		
		# Validate required fields
		required_fields = ["customer_id", "file_name", "file_id", "file_size"]
		for field in required_fields:
			if not data.get(field):
				frappe.throw(f"{field} is required")
				
		customer_id = data.get("customer_id")
		
		# Verify customer exists and is active
		customer = frappe.get_doc("SaaS Customer", customer_id)
		if customer.subscription_status not in ["Active", "Trial"]:
			frappe.throw("Customer subscription is not active")
			
		# Check quota
		if not customer.check_usage_quota():
			frappe.throw("Monthly processing quota exceeded")
			
		# Generate job ID
		job_id = frappe.generate_hash(length=16)
		
		# Create processing job
		job = frappe.get_doc({
			"doctype": "Processing Job",
			"job_id": job_id,
			"customer": customer_id,
			"file_name": data.get("file_name"),
			"file_id": data.get("file_id"),
			"file_url": f"https://drive.google.com/file/d/{data.get('file_id')}/view",
			"file_size": int(data.get("file_size", 0)),
			"file_type": data.get("file_type", "unknown"),
			"processing_status": "Queued",
			"started_at": now(),
			"complexity_score": data.get("complexity_score", 0.5),
			"quality_score": data.get("quality_score", 0.8),
			"extraction_engine": data.get("recommended_engine", "azure"),
			"billable": 1
		})
		
		job.insert(ignore_permissions=True)
		
		# Increment customer usage
		customer.increment_usage()
		
		return {
			"success": True,
			"job_id": job_id,
			"job_name": job.name,
			"message": "Processing job created successfully"
		}
		
	except Exception as e:
		frappe.log_error(f"Error in create_processing_job: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_job_status():
	"""
	n8n API endpoint to update processing job status
	Called during various stages of n8n workflow
	"""
	try:
		data = frappe.local.form_dict
		job_id = data.get("job_id")
		status = data.get("status")
		
		if not job_id or not status:
			frappe.throw("job_id and status are required")
			
		# Find and update job
		job_name = frappe.db.get_value("Processing Job", {"job_id": job_id}, "name")
		if not job_name:
			frappe.throw("Processing job not found")
			
		job = frappe.get_doc("Processing Job", job_name)
		job.processing_status = status
		
		if status == "Processing":
			job.started_at = now()
		elif status in ["Completed", "Failed"]:
			job.completed_at = now()
			if job.started_at:
				from frappe.utils import time_diff_in_seconds
				job.processing_time = time_diff_in_seconds(job.completed_at, job.started_at)
				
		if data.get("error_message"):
			job.error_message = data.get("error_message")
			
		if data.get("extraction_engine"):
			job.extraction_engine = data.get("extraction_engine")
			
		job.save(ignore_permissions=True)
		
		return {"success": True, "message": "Job status updated"}
		
	except Exception as e:
		frappe.log_error(f"Error in update_job_status: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def store_processing_result():
	"""
	n8n API endpoint to store final processing results
	Called when n8n completes data extraction and validation
	"""
	try:
		data = frappe.local.form_dict
		job_id = data.get("job_id")
		
		if not job_id:
			frappe.throw("job_id is required")
			
		# Find job
		job_name = frappe.db.get_value("Processing Job", {"job_id": job_id}, "name")
		if not job_name:
			frappe.throw("Processing job not found")
			
		job = frappe.get_doc("Processing Job", job_name)
		
		# Update job with extraction results
		if data.get("extracted_data"):
			job.extracted_data = json.dumps(data.get("extracted_data"))
			
			# Parse and store structured invoice data
			extracted = data.get("extracted_data")
			
			# Store vendor information
			vendor_info = extracted.get("vendor", {})
			job.vendor_name = vendor_info.get("name")
			job.vendor_address = vendor_info.get("address")
			job.vendor_tax_id = vendor_info.get("tax_id")
			
			# Store invoice details
			invoice_info = extracted.get("invoice", {})
			job.invoice_number = invoice_info.get("number")
			job.invoice_date = invoice_info.get("date")
			job.due_date = invoice_info.get("due_date")
			
			# Store amounts
			amounts = extracted.get("amounts", {})
			job.total_amount = amounts.get("total")
			job.tax_amount = amounts.get("tax")
			job.subtotal_amount = amounts.get("subtotal")
			job.currency_code = amounts.get("currency", "USD")
			
			# Store terms
			terms = extracted.get("terms", {})
			job.payment_terms = terms.get("payment_terms")
			job.po_number = terms.get("po_number")
			
			# Store line items as JSON for now (can be normalized later)
			if extracted.get("line_items"):
				job.line_items_data = json.dumps(extracted.get("line_items"))
				job.line_items_count = len(extracted.get("line_items"))
		
		# Update validation status
		if data.get("validation_status"):
			job.validation_status = data.get("validation_status")
			
		if data.get("validation_errors"):
			job.validation_errors = data.get("validation_errors")
			
		if data.get("confidence_score"):
			job.confidence_score = float(data.get("confidence_score"))
			
		# Update completion status
		job.processing_status = "Completed"
		job.completed_at = now()
		
		if job.started_at:
			from frappe.utils import time_diff_in_seconds
			job.processing_time = time_diff_in_seconds(job.completed_at, job.started_at)
		
		# Handle accounting import status
		if data.get("accounting_import_status"):
			job.accounting_import_status = data.get("accounting_import_status")
			
		if data.get("accounting_import_id"):
			job.accounting_import_id = data.get("accounting_import_id")
			
		job.save(ignore_permissions=True)
		
		# Send completion notification to customer
		try:
			customer = frappe.get_doc("SaaS Customer", job.customer)
			frappe.sendmail(
				recipients=[customer.email],
				subject=f"Invoice Processing Complete - {job.file_name}",
				template="processing_complete",
				args={
					"customer_name": customer.customer_name,
					"file_name": job.file_name,
					"processing_status": job.processing_status,
					"validation_status": job.validation_status,
					"confidence_score": job.confidence_score,
					"dashboard_url": f"{frappe.utils.get_url()}/dashboard"
				}
			)
		except Exception as email_error:
			frappe.log_error(f"Failed to send completion email: {str(email_error)}")
		
		return {
			"success": True,
			"job_name": job.name,
			"message": "Processing result stored successfully"
		}
		
	except Exception as e:
		frappe.log_error(f"Error in store_processing_result: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def update_usage_tracking():
	"""
	n8n API endpoint to update customer usage statistics
	Called by n8n for billing and analytics
	"""
	try:
		data = frappe.local.form_dict
		customer_id = data.get("customer_id")
		
		if not customer_id:
			frappe.throw("customer_id is required")
			
		# Get or create usage tracking record for current month
		from frappe.utils import get_first_day
		current_month = get_first_day(nowdate()).strftime("%Y-%m")
		
		usage_tracking = frappe.db.get_value("Usage Tracking", 
			{"customer": customer_id, "month": current_month}, "name")
			
		if usage_tracking:
			usage_doc = frappe.get_doc("Usage Tracking", usage_tracking)
		else:
			customer = frappe.get_doc("SaaS Customer", customer_id)
			usage_doc = frappe.get_doc({
				"doctype": "Usage Tracking",
				"customer": customer_id,
				"month": current_month,
				"plan_limit": customer.usage_limit,
				"processed_count": 0,
				"successful_count": 0,
				"failed_count": 0,
				"overage_count": 0,
				"overage_charges": 0,
				"billing_status": "Pending"
			})
			usage_doc.insert(ignore_permissions=True)
		
		# Update counters based on job status
		job_status = data.get("job_status", "completed")
		
		if job_status == "completed":
			usage_doc.processed_count += 1
			usage_doc.successful_count += 1
		elif job_status == "failed":
			usage_doc.processed_count += 1
			usage_doc.failed_count += 1
		
		# Calculate overage
		if usage_doc.processed_count > usage_doc.plan_limit:
			usage_doc.overage_count = usage_doc.processed_count - usage_doc.plan_limit
			
			# Calculate overage charges (if applicable)
			if data.get("overage_rate"):
				usage_doc.overage_charges = usage_doc.overage_count * float(data.get("overage_rate"))
		
		usage_doc.last_updated = now()
		usage_doc.save(ignore_permissions=True)
		
		return {
			"success": True,
			"message": "Usage tracking updated",
			"current_usage": usage_doc.processed_count,
			"overage_count": usage_doc.overage_count
		}
		
	except Exception as e:
		frappe.log_error(f"Error in update_usage_tracking: {str(e)}")
		return {"success": False, "error": str(e)}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def log_processing_event():
	"""
	n8n API endpoint to log processing events for debugging and analytics
	"""
	try:
		data = frappe.local.form_dict
		
		# Create a processing log entry
		log_entry = frappe.get_doc({
			"doctype": "Processing Log",
			"job_id": data.get("job_id"),
			"customer": data.get("customer_id"),
			"event_type": data.get("event_type", "info"),
			"event_message": data.get("message", ""),
			"event_data": json.dumps(data.get("event_data", {})) if data.get("event_data") else None,
			"timestamp": now()
		})
		
		log_entry.insert(ignore_permissions=True)
		
		return {"success": True, "message": "Event logged"}
		
	except Exception as e:
		frappe.log_error(f"Error in log_processing_event: {str(e)}")
		return {"success": False, "error": str(e)}


# Authentication helper for API endpoints
def validate_api_request():
	"""Validate API request authentication"""
	# This can be enhanced with proper API key validation
	# For now, we'll use the allow_guest=True flag
	pass


# Utility functions for n8n integration
@frappe.whitelist()
def get_n8n_webhook_urls():
	"""Get configured n8n webhook URLs for customer setup"""
	settings = frappe.get_single("Invoice Processing Settings")
	
	return {
		"base_url": settings.n8n_webhook_base_url,
		"endpoints": {
			"user_lookup": f"{settings.n8n_webhook_base_url}/webhook/user-lookup",
			"job_creation": f"{settings.n8n_webhook_base_url}/webhook/create-job",
			"job_update": f"{settings.n8n_webhook_base_url}/webhook/update-job",
			"store_result": f"{settings.n8n_webhook_base_url}/webhook/store-result"
		}
	}


@frappe.whitelist()
def test_n8n_connection():
	"""Test connection to n8n workflow"""
	try:
		settings = frappe.get_single("Invoice Processing Settings")
		
		# Make a test request to n8n
		import requests
		
		test_data = {
			"test": True,
			"timestamp": now()
		}
		
		response = requests.post(
			f"{settings.n8n_webhook_base_url}/webhook/test",
			json=test_data,
			timeout=10
		)
		
		if response.status_code == 200:
			return {"success": True, "message": "n8n connection successful"}
		else:
			return {"success": False, "error": f"HTTP {response.status_code}"}
			
	except Exception as e:
		return {"success": False, "error": str(e)}