# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, time_diff_in_seconds
import json


class ProcessingJob(Document):
	def validate(self):
		"""Validate processing job data"""
		self.validate_customer_permissions()
		self.update_processing_time()
		
	def validate_customer_permissions(self):
		"""Ensure user can only access their own jobs"""
		if frappe.session.user != "Administrator":
			user_email = frappe.session.user
			customer_email = frappe.db.get_value("SaaS Customer", self.customer, "email")
			
			if user_email != customer_email and not frappe.has_permission("Processing Job", "write"):
				frappe.throw("Access denied")
				
	def update_processing_time(self):
		"""Calculate processing time if completed"""
		if self.started_at and self.completed_at:
			self.processing_time = time_diff_in_seconds(self.completed_at, self.started_at)
			
	def mark_as_processing(self):
		"""Mark job as processing"""
		self.processing_status = "Processing"
		self.started_at = now()
		self.save(ignore_permissions=True)
		
	def mark_as_completed(self, extracted_data=None):
		"""Mark job as completed"""
		self.processing_status = "Completed"
		self.completed_at = now()
		
		if extracted_data:
			self.store_extracted_data(extracted_data)
			
		self.save(ignore_permissions=True)
		self.notify_customer_completion()
		
	def mark_as_failed(self, error_message=None):
		"""Mark job as failed"""
		self.processing_status = "Failed"
		self.completed_at = now()
		
		if error_message:
			self.error_message = error_message
			
		self.save(ignore_permissions=True)
		self.notify_customer_failure()
		
	def store_extracted_data(self, extracted_data):
		"""Store extracted invoice data"""
		if not extracted_data:
			return
			
		# Store raw JSON data
		self.extracted_data = json.dumps(extracted_data)
		
		# Parse and store structured data
		vendor_info = extracted_data.get("vendor", {})
		self.vendor_name = vendor_info.get("name")
		self.vendor_address = vendor_info.get("address")
		self.vendor_tax_id = vendor_info.get("tax_id")
		
		invoice_info = extracted_data.get("invoice", {})
		self.invoice_number = invoice_info.get("number")
		self.invoice_date = invoice_info.get("date")
		self.due_date = invoice_info.get("due_date")
		
		amounts = extracted_data.get("amounts", {})
		self.total_amount = amounts.get("total")
		self.tax_amount = amounts.get("tax")
		self.subtotal_amount = amounts.get("subtotal")
		self.currency_code = amounts.get("currency", "USD")
		
		terms = extracted_data.get("terms", {})
		self.payment_terms = terms.get("payment_terms")
		self.po_number = terms.get("po_number")
		
		# Store line items
		line_items = extracted_data.get("line_items", [])
		if line_items:
			self.line_items_data = json.dumps(line_items)
			self.line_items_count = len(line_items)
			
	def get_line_items(self):
		"""Get parsed line items"""
		if self.line_items_data:
			try:
				return json.loads(self.line_items_data)
			except:
				return []
		return []
		
	def get_extracted_data(self):
		"""Get parsed extracted data"""
		if self.extracted_data:
			try:
				return json.loads(self.extracted_data)
			except:
				return {}
		return {}
		
	def retry_processing(self):
		"""Retry failed processing"""
		if self.processing_status != "Failed":
			frappe.throw("Can only retry failed jobs")
			
		self.retry_count = (self.retry_count or 0) + 1
		if self.retry_count > 3:
			frappe.throw("Maximum retry attempts exceeded")
			
		self.processing_status = "Retry"
		self.error_message = None
		self.save(ignore_permissions=True)
		
		# Trigger n8n retry (this would call n8n API)
		self.trigger_n8n_retry()
		
	def trigger_n8n_retry(self):
		"""Trigger n8n workflow for retry"""
		try:
			settings = frappe.get_single("Invoice Processing Settings")
			
			# Make API call to n8n retry endpoint
			import requests
			
			retry_data = {
				"job_id": self.job_id,
				"retry_count": self.retry_count,
				"file_id": self.file_id,
				"customer_id": self.customer
			}
			
			response = requests.post(
				f"{settings.n8n_webhook_base_url}/webhook/retry-job",
				json=retry_data,
				timeout=30
			)
			
			if response.status_code != 200:
				frappe.log_error(f"Failed to trigger n8n retry: {response.text}")
				
		except Exception as e:
			frappe.log_error(f"Error triggering n8n retry: {str(e)}")
			
	def notify_customer_completion(self):
		"""Send completion notification to customer"""
		try:
			customer = frappe.get_doc("SaaS Customer", self.customer)
			
			frappe.sendmail(
				recipients=[customer.email],
				subject=f"Invoice Processing Complete - {self.file_name}",
				template="processing_complete",
				args={
					"customer_name": customer.customer_name,
					"file_name": self.file_name,
					"processing_status": self.processing_status,
					"validation_status": self.validation_status,
					"confidence_score": self.confidence_score,
					"invoice_number": self.invoice_number,
					"vendor_name": self.vendor_name,
					"total_amount": self.total_amount,
					"dashboard_url": f"{frappe.utils.get_url()}/dashboard",
					"job_url": f"{frappe.utils.get_url()}/app/processing-job/{self.name}"
				}
			)
		except Exception as e:
			frappe.log_error(f"Failed to send completion notification: {str(e)}")
			
	def notify_customer_failure(self):
		"""Send failure notification to customer"""
		try:
			customer = frappe.get_doc("SaaS Customer", self.customer)
			
			frappe.sendmail(
				recipients=[customer.email],
				subject=f"Invoice Processing Failed - {self.file_name}",
				template="processing_failed",
				args={
					"customer_name": customer.customer_name,
					"file_name": self.file_name,
					"error_message": self.error_message or "Unknown error occurred",
					"retry_count": self.retry_count,
					"support_email": "support@yourcompany.com",
					"dashboard_url": f"{frappe.utils.get_url()}/dashboard"
				}
			)
		except Exception as e:
			frappe.log_error(f"Failed to send failure notification: {str(e)}")
			
	def export_to_accounting_system(self):
		"""Export processed data to accounting system (manual trigger)"""
		if self.processing_status != "Completed":
			frappe.throw("Can only export completed jobs")
			
		if not self.extracted_data:
			frappe.throw("No extracted data to export")
			
		# Get customer's accounting integration
		accounting_integration = frappe.db.get_value("Accounting Integration",
			{"customer": self.customer}, "name")
			
		if not accounting_integration:
			frappe.throw("No accounting integration configured")
			
		# This would trigger the accounting export process
		# For now, we'll mark as pending export
		self.accounting_import_status = "Pending"
		self.save(ignore_permissions=True)
		
		frappe.msgprint("Export to accounting system initiated")


@frappe.whitelist()
def get_customer_jobs(customer_name=None, limit=20):
	"""Get processing jobs for a customer"""
	if not customer_name:
		# Get customer by current user email
		customer_name = frappe.db.get_value("SaaS Customer", 
			{"email": frappe.session.user}, "name")
			
	if not customer_name:
		return []
		
	# Check permissions
	customer = frappe.get_doc("SaaS Customer", customer_name)
	if frappe.session.user != customer.email and not frappe.has_permission("Processing Job", "read"):
		frappe.throw("Access denied")
		
	jobs = frappe.get_all("Processing Job",
		filters={"customer": customer_name},
		fields=["name", "job_id", "file_name", "processing_status", "validation_status",
				"started_at", "completed_at", "processing_time", "extraction_engine",
				"vendor_name", "invoice_number", "total_amount", "confidence_score"],
		order_by="creation desc",
		limit=limit
	)
	
	return jobs


@frappe.whitelist()
def get_job_statistics(customer_name=None):
	"""Get job statistics for dashboard"""
	if not customer_name:
		customer_name = frappe.db.get_value("SaaS Customer", 
			{"email": frappe.session.user}, "name")
			
	if not customer_name:
		return {}
		
	from frappe.utils import get_first_day, get_last_day, today
	
	# Current month stats
	start_date = get_first_day(today())
	end_date = get_last_day(today())
	
	stats = frappe.db.sql("""
		SELECT 
			COUNT(*) as total_jobs,
			SUM(CASE WHEN processing_status = 'Completed' THEN 1 ELSE 0 END) as completed,
			SUM(CASE WHEN processing_status = 'Failed' THEN 1 ELSE 0 END) as failed,
			SUM(CASE WHEN processing_status IN ('Queued', 'Processing') THEN 1 ELSE 0 END) as in_progress,
			AVG(processing_time) as avg_processing_time,
			AVG(confidence_score) as avg_confidence_score
		FROM `tabProcessing Job`
		WHERE customer = %s AND DATE(creation) BETWEEN %s AND %s
	""", (customer_name, start_date, end_date), as_dict=1)
	
	return stats[0] if stats else {
		"total_jobs": 0, "completed": 0, "failed": 0, "in_progress": 0,
		"avg_processing_time": 0, "avg_confidence_score": 0
	}


@frappe.whitelist()
def retry_failed_job(job_name):
	"""Retry a failed processing job"""
	job = frappe.get_doc("Processing Job", job_name)
	
	# Check permissions
	customer = frappe.get_doc("SaaS Customer", job.customer)
	if frappe.session.user != customer.email and not frappe.has_permission("Processing Job", "write"):
		frappe.throw("Access denied")
		
	job.retry_processing()
	return {"success": True, "message": "Job retry initiated"}