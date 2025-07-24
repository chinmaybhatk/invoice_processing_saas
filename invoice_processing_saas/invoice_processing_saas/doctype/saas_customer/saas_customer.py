# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, add_days, get_datetime, nowdate
import secrets
import string


class SaaSCustomer(Document):
	def before_insert(self):
		"""Set default values before inserting new customer"""
		self.generate_api_credentials()
		self.set_trial_period()
		self.set_usage_limit_from_plan()
		
	def after_insert(self):
		"""Post-creation tasks"""
		self.create_user_if_needed()
		self.send_welcome_email()
		
	def validate(self):
		"""Validate customer data"""
		self.validate_email()
		self.validate_subscription_dates()
		self.update_usage_limit_if_plan_changed()
		
	def generate_api_credentials(self):
		"""Generate API key and webhook secret for n8n integration"""
		if not self.api_key:
			# Generate secure API key
			alphabet = string.ascii_letters + string.digits
			self.api_key = ''.join(secrets.choice(alphabet) for _ in range(32))
			
		if not self.webhook_secret:
			# Generate webhook secret for n8n authentication
			self.webhook_secret = ''.join(secrets.choice(alphabet) for _ in range(16))
			
	def set_trial_period(self):
		"""Set trial period for new customers"""
		if not self.subscription_start_date:
			self.subscription_start_date = today()
			
		if not self.trial_end_date and self.subscription_status == "Trial":
			# Get trial days from subscription plan
			if self.subscription_plan:
				plan = frappe.get_doc("Subscription Plan", self.subscription_plan)
				trial_days = plan.trial_days or 14
				self.trial_end_date = add_days(today(), trial_days)
				
	def set_usage_limit_from_plan(self):
		"""Set usage limit based on subscription plan"""
		if self.subscription_plan and not self.usage_limit:
			plan = frappe.get_doc("Subscription Plan", self.subscription_plan)
			self.usage_limit = plan.processing_limit
			
	def validate_email(self):
		"""Ensure email is unique and valid"""
		if self.email:
			existing = frappe.db.get_value("SaaS Customer", 
				{"email": self.email, "name": ["!=", self.name]}, "name")
			if existing:
				frappe.throw(f"Customer with email {self.email} already exists")
				
	def validate_subscription_dates(self):
		"""Validate subscription date logic"""
		if self.subscription_start_date and self.subscription_end_date:
			if get_datetime(self.subscription_end_date) <= get_datetime(self.subscription_start_date):
				frappe.throw("Subscription end date must be after start date")
				
	def update_usage_limit_if_plan_changed(self):
		"""Update usage limit when plan changes"""
		if self.has_value_changed("subscription_plan") and self.subscription_plan:
			plan = frappe.get_doc("Subscription Plan", self.subscription_plan)
			self.usage_limit = plan.processing_limit
			
	def create_user_if_needed(self):
		"""Create a portal user for the customer"""
		if not frappe.db.exists("User", self.email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": self.email,
				"first_name": self.customer_name.split()[0] if self.customer_name else "Customer",
				"user_type": "Website User",
				"send_welcome_email": 0  # We'll send our custom welcome email
			})
			
			# Add customer role
			user.append("roles", {"role": "Customer"})
			user.insert(ignore_permissions=True)
			
			# Link user to customer
			self.user = user.name
			
	def send_welcome_email(self):
		"""Send welcome email to new customer"""
		if self.created_by_webform:
			try:
				frappe.sendmail(
					recipients=[self.email],
					subject="Welcome to Invoice Processing SaaS!",
					template="welcome_customer",
					args={
						"customer_name": self.customer_name,
						"trial_end_date": self.trial_end_date,
						"dashboard_url": f"{frappe.utils.get_url()}/dashboard",
						"api_key": self.api_key
					}
				)
			except Exception as e:
				frappe.log_error(f"Failed to send welcome email to {self.email}: {str(e)}")
				
	def check_usage_quota(self):
		"""Check if customer has available quota"""
		if self.current_usage >= self.usage_limit:
			if not self.overage_allowed:
				frappe.throw("Monthly processing quota exceeded. Please upgrade your plan.")
			return False
		return True
		
	def increment_usage(self):
		"""Increment current usage counter"""
		self.current_usage = (self.current_usage or 0) + 1
		self.total_processed = (self.total_processed or 0) + 1
		self.last_activity = frappe.utils.now()
		self.save(ignore_permissions=True)
		
		# Check if approaching limit
		usage_percentage = (self.current_usage / self.usage_limit) * 100
		if usage_percentage >= 80 and usage_percentage < 85:
			self.send_usage_warning(80)
		elif usage_percentage >= 90 and usage_percentage < 95:
			self.send_usage_warning(90)
		elif usage_percentage >= 100:
			self.send_usage_warning(100)
			
	def send_usage_warning(self, percentage):
		"""Send usage warning email"""
		try:
			subject = f"Usage Alert: {percentage}% of quota used"
			if percentage >= 100:
				subject = "Quota Exceeded - Action Required"
				
			frappe.sendmail(
				recipients=[self.email],
				subject=subject,
				template="usage_warning",
				args={
					"customer_name": self.customer_name,
					"current_usage": self.current_usage,
					"usage_limit": self.usage_limit,
					"percentage": percentage,
					"upgrade_url": f"{frappe.utils.get_url()}/billing"
				}
			)
		except Exception as e:
			frappe.log_error(f"Failed to send usage warning to {self.email}: {str(e)}")
			
	def reset_monthly_usage(self):
		"""Reset monthly usage counter (called by scheduled job)"""
		self.current_usage = 0
		self.save(ignore_permissions=True)
		
	def get_integration_status(self):
		"""Get status of all integrations"""
		status = {
			"drive": "Not Connected",
			"accounting": "Not Connected",
			"overall": "Incomplete"
		}
		
		# Check Drive Integration
		drive_integration = frappe.db.get_value("Drive Integration", 
			{"customer": self.name}, ["integration_status", "setup_completed"])
		if drive_integration:
			status["drive"] = drive_integration[0] if drive_integration[1] else "Setup Required"
			
		# Check Accounting Integration
		accounting_integration = frappe.db.get_value("Accounting Integration",
			{"customer": self.name}, ["integration_status"])
		if accounting_integration:
			status["accounting"] = accounting_integration[0]
			
		# Determine overall status
		if status["drive"] == "Active" and status["accounting"] == "Connected":
			status["overall"] = "Complete"
		elif status["drive"] in ["Active", "Setup Required"] or status["accounting"] in ["Connected", "Setup Required"]:
			status["overall"] = "Partial"
			
		return status
		
	def get_recent_jobs(self, limit=10):
		"""Get recent processing jobs"""
		return frappe.get_all("Processing Job",
			filters={"customer": self.name},
			fields=["name", "file_name", "processing_status", "completed_at", "extraction_engine"],
			order_by="creation desc",
			limit=limit
		)
		
	def get_monthly_stats(self):
		"""Get monthly processing statistics"""
		from frappe.utils import get_first_day, get_last_day
		
		start_date = get_first_day(today())
		end_date = get_last_day(today())
		
		stats = frappe.db.sql("""
			SELECT 
				COUNT(*) as total_jobs,
				SUM(CASE WHEN processing_status = 'Completed' THEN 1 ELSE 0 END) as successful,
				SUM(CASE WHEN processing_status = 'Failed' THEN 1 ELSE 0 END) as failed,
				AVG(processing_time) as avg_processing_time
			FROM `tabProcessing Job`
			WHERE customer = %s AND DATE(creation) BETWEEN %s AND %s
		""", (self.name, start_date, end_date), as_dict=1)
		
		return stats[0] if stats else {
			"total_jobs": 0, "successful": 0, "failed": 0, "avg_processing_time": 0
		}
		

@frappe.whitelist()
def get_customer_dashboard_data(customer_name=None):
	"""API endpoint for customer dashboard data"""
	if not customer_name:
		# Get customer by current user email
		customer_name = frappe.db.get_value("SaaS Customer", {"email": frappe.session.user}, "name")
		
	if not customer_name:
		frappe.throw("Customer not found")
		
	customer = frappe.get_doc("SaaS Customer", customer_name)
	
	# Check permissions
	if frappe.session.user != customer.email and not frappe.has_permission("SaaS Customer", "read", customer_name):
		frappe.throw("Not permitted")
		
	return {
		"customer_info": {
			"name": customer.customer_name,
			"email": customer.email,
			"subscription_plan": customer.subscription_plan,
			"subscription_status": customer.subscription_status,
			"trial_end_date": customer.trial_end_date,
			"current_usage": customer.current_usage,
			"usage_limit": customer.usage_limit,
			"usage_percentage": (customer.current_usage / customer.usage_limit * 100) if customer.usage_limit else 0
		},
		"integration_status": customer.get_integration_status(),
		"recent_jobs": customer.get_recent_jobs(),
		"monthly_stats": customer.get_monthly_stats()
	}
	

@frappe.whitelist()
def check_quota_available(folder_id):
	"""API endpoint for n8n to check if customer has quota available"""
	# Get customer by drive folder
	customer_name = frappe.db.get_value("Drive Integration", {"drive_folder_id": folder_id}, "customer")
	
	if not customer_name:
		return {"quota_available": False, "error": "Customer not found"}
		
	customer = frappe.get_doc("SaaS Customer", customer_name)
	
	# Check subscription status
	if customer.subscription_status not in ["Active", "Trial"]:
		return {"quota_available": False, "error": "Subscription inactive"}
		
	# Check quota
	quota_available = customer.current_usage < customer.usage_limit or customer.overage_allowed
	
	return {
		"quota_available": quota_available,
		"current_usage": customer.current_usage,
		"usage_limit": customer.usage_limit,
		"customer_name": customer.customer_name,
		"subscription_status": customer.subscription_status
	}
