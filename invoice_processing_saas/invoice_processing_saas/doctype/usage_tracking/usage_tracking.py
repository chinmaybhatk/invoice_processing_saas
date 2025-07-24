# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import now, get_first_day, get_last_day, add_days


class UsageTracking(Document):
	def validate(self):
		"""Validate usage tracking data"""
		self.validate_unique_customer_month()
		self.calculate_total_charges()
		self.validate_customer_permissions()
		
	def validate_unique_customer_month(self):
		"""Ensure one record per customer per month"""
		existing = frappe.db.get_value("Usage Tracking",
			{"customer": self.customer, "month": self.month, "name": ["!=", self.name]},
			"name")
			
		if existing:
			frappe.throw(f"Usage tracking already exists for {self.customer} - {self.month}")
			
	def calculate_total_charges(self):
		"""Calculate total charges including overage"""
		# Get base subscription cost
		customer = frappe.get_doc("SaaS Customer", self.customer)
		plan = frappe.get_doc("Subscription Plan", customer.subscription_plan)
		
		base_cost = plan.monthly_price
		overage_cost = self.overage_charges or 0
		
		self.total_charges = base_cost + overage_cost
		
	def validate_customer_permissions(self):
		"""Ensure user can only access their own usage data"""
		if frappe.session.user != "Administrator":
			user_email = frappe.session.user
			customer_email = frappe.db.get_value("SaaS Customer", self.customer, "email")
			
			if user_email != customer_email and not frappe.has_permission("Usage Tracking", "read"):
				frappe.throw("Access denied")
				
	def increment_usage(self, engine="azure", processing_time=None, confidence_score=None):
		"""Increment usage counters"""
		self.processed_count = (self.processed_count or 0) + 1
		
		# Update engine-specific counters
		if engine == "openai":
			self.openai_usage = (self.openai_usage or 0) + 1
		elif engine == "azure":
			self.azure_usage = (self.azure_usage or 0) + 1
		elif engine == "manual":
			self.manual_processing = (self.manual_processing or 0) + 1
			
		# Calculate overage
		if self.processed_count > self.plan_limit:
			self.overage_count = self.processed_count - self.plan_limit
			
			# Calculate overage charges
			customer = frappe.get_doc("SaaS Customer", self.customer)
			plan = frappe.get_doc("Subscription Plan", customer.subscription_plan)
			
			if plan.overage_rate:
				self.overage_charges = self.overage_count * plan.overage_rate
				
		# Update averages
		if processing_time:
			current_avg = self.avg_processing_time or 0
			self.avg_processing_time = ((current_avg * (self.processed_count - 1)) + processing_time) / self.processed_count
			
		if confidence_score:
			current_avg = self.avg_confidence_score or 0
			self.avg_confidence_score = ((current_avg * (self.processed_count - 1)) + confidence_score) / self.processed_count
			
		self.last_updated = now()
		self.save(ignore_permissions=True)
		
	def mark_successful(self):
		"""Mark a processing as successful"""
		self.successful_count = (self.successful_count or 0) + 1
		self.save(ignore_permissions=True)
		
	def mark_failed(self):
		"""Mark a processing as failed"""
		self.failed_count = (self.failed_count or 0) + 1
		self.save(ignore_permissions=True)
		
	def get_success_rate(self):
		"""Calculate success rate percentage"""
		if not self.processed_count:
			return 0
			
		return (self.successful_count / self.processed_count) * 100
		
	def get_usage_percentage(self):
		"""Calculate usage percentage vs plan limit"""
		if not self.plan_limit:
			return 0
			
		return min((self.processed_count / self.plan_limit) * 100, 100)
		
	def is_over_limit(self):
		"""Check if usage is over plan limit"""
		return self.processed_count > self.plan_limit
		
	def generate_invoice(self):
		"""Generate invoice for this month's usage"""
		if self.invoice_generated:
			frappe.throw("Invoice already generated for this month")
			
		# Create invoice record
		invoice_id = f"INV-{self.customer}-{self.month}"
		
		self.invoice_generated = 1
		self.invoice_id = invoice_id
		self.invoice_date = now().split()[0]  # Current date
		self.due_date = add_days(self.invoice_date, 30)  # 30 days payment terms
		self.billing_status = "Billed"
		self.payment_status = "Pending"
		
		self.save(ignore_permissions=True)
		
		# Send invoice email to customer
		self.send_invoice_email()
		
		return invoice_id
		
	def send_invoice_email(self):
		"""Send invoice email to customer"""
		try:
			customer = frappe.get_doc("SaaS Customer", self.customer)
			
			frappe.sendmail(
				recipients=[customer.email],
				subject=f"Invoice {self.invoice_id} - {self.month}",
				template="monthly_invoice",
				args={
					"customer_name": customer.customer_name,
					"invoice_id": self.invoice_id,
					"month": self.month,
					"processed_count": self.processed_count,
					"plan_limit": self.plan_limit,
					"overage_count": self.overage_count,
					"overage_charges": self.overage_charges,
					"total_charges": self.total_charges,
					"due_date": self.due_date,
					"payment_url": f"{frappe.utils.get_url()}/billing"
				}
			)
			
		except Exception as e:
			frappe.log_error(f"Failed to send invoice email: {str(e)}")


@frappe.whitelist()
def get_customer_usage_data(customer_name=None, months=6):
	"""Get customer usage data for dashboard"""
	if not customer_name:
		customer_name = frappe.db.get_value("SaaS Customer",
			{"email": frappe.session.user}, "name")
			
	if not customer_name:
		return []
		
	# Check permissions
	customer = frappe.get_doc("SaaS Customer", customer_name)
	if frappe.session.user != customer.email and not frappe.has_permission("Usage Tracking", "read"):
		frappe.throw("Access denied")
		
	usage_data = frappe.get_all("Usage Tracking",
		filters={"customer": customer_name},
		fields=["month", "processed_count", "successful_count", "failed_count",
				"plan_limit", "overage_count", "overage_charges", "total_charges",
				"openai_usage", "azure_usage", "avg_processing_time", "avg_confidence_score"],
		order_by="month desc",
		limit=months
	)
	
	# Add calculated fields
	for usage in usage_data:
		usage["success_rate"] = (usage["successful_count"] / usage["processed_count"] * 100) if usage["processed_count"] else 0
		usage["usage_percentage"] = min((usage["processed_count"] / usage["plan_limit"] * 100), 100) if usage["plan_limit"] else 0
		usage["is_over_limit"] = usage["processed_count"] > usage["plan_limit"]
		
	return usage_data


@frappe.whitelist()
def get_or_create_current_month_usage(customer_name):
	"""Get or create usage tracking for current month"""
	from frappe.utils import today, get_first_day
	
	current_month = get_first_day(today()).strftime("%Y-%m")
	
	existing = frappe.db.get_value("Usage Tracking",
		{"customer": customer_name, "month": current_month}, "name")
		
	if existing:
		return frappe.get_doc("Usage Tracking", existing)
		
	# Create new usage tracking record
	customer = frappe.get_doc("SaaS Customer", customer_name)
	
	usage_doc = frappe.get_doc({
		"doctype": "Usage Tracking",
		"customer": customer_name,
		"month": current_month,
		"plan_limit": customer.usage_limit,
		"reset_date": get_first_day(today()),
		"billing_status": "Pending"
	})
	
	usage_doc.insert(ignore_permissions=True)
	return usage_doc