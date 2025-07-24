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
				frappe.throw("Monthly processing quota exceeded. Please upgrade your plan.")\n			return False\n		return True\n		\n	def increment_usage(self):\n		\"\"\"Increment current usage counter\"\"\"\n		self.current_usage = (self.current_usage or 0) + 1\n		self.total_processed = (self.total_processed or 0) + 1\n		self.last_activity = frappe.utils.now()\n		self.save(ignore_permissions=True)\n		\n		# Check if approaching limit\n		usage_percentage = (self.current_usage / self.usage_limit) * 100\n		if usage_percentage >= 80 and usage_percentage < 85:\n			self.send_usage_warning(80)\n		elif usage_percentage >= 90 and usage_percentage < 95:\n			self.send_usage_warning(90)\n		elif usage_percentage >= 100:\n			self.send_usage_warning(100)\n			\n	def send_usage_warning(self, percentage):\n		\"\"\"Send usage warning email\"\"\"\n		try:\n			subject = f\"Usage Alert: {percentage}% of quota used\"\n			if percentage >= 100:\n				subject = \"Quota Exceeded - Action Required\"\n				\n			frappe.sendmail(\n				recipients=[self.email],\n				subject=subject,\n				template=\"usage_warning\",\n				args={\n					\"customer_name\": self.customer_name,\n					\"current_usage\": self.current_usage,\n					\"usage_limit\": self.usage_limit,\n					\"percentage\": percentage,\n					\"upgrade_url\": f\"{frappe.utils.get_url()}/billing\"\n				}\n			)\n		except Exception as e:\n			frappe.log_error(f\"Failed to send usage warning to {self.email}: {str(e)}\")\n			\n	def reset_monthly_usage(self):\n		\"\"\"Reset monthly usage counter (called by scheduled job)\"\"\"\n		self.current_usage = 0\n		self.save(ignore_permissions=True)\n		\n	def get_integration_status(self):\n		\"\"\"Get status of all integrations\"\"\"\n		status = {\n			\"drive\": \"Not Connected\",\n			\"accounting\": \"Not Connected\",\n			\"overall\": \"Incomplete\"\n		}\n		\n		# Check Drive Integration\n		drive_integration = frappe.db.get_value(\"Drive Integration\", \n			{\"customer\": self.name}, [\"integration_status\", \"setup_completed\"])\n		if drive_integration:\n			status[\"drive\"] = drive_integration[0] if drive_integration[1] else \"Setup Required\"\n			\n		# Check Accounting Integration\n		accounting_integration = frappe.db.get_value(\"Accounting Integration\",\n			{\"customer\": self.name}, [\"integration_status\"])\n		if accounting_integration:\n			status[\"accounting\"] = accounting_integration[0]\n			\n		# Determine overall status\n		if status[\"drive\"] == \"Active\" and status[\"accounting\"] == \"Connected\":\n			status[\"overall\"] = \"Complete\"\n		elif status[\"drive\"] in [\"Active\", \"Setup Required\"] or status[\"accounting\"] in [\"Connected\", \"Setup Required\"]:\n			status[\"overall\"] = \"Partial\"\n			\n		return status\n		\n	def get_recent_jobs(self, limit=10):\n		\"\"\"Get recent processing jobs\"\"\"\n		return frappe.get_all(\"Processing Job\",\n			filters={\"customer\": self.name},\n			fields=[\"name\", \"file_name\", \"processing_status\", \"completed_at\", \"extraction_engine\"],\n			order_by=\"creation desc\",\n			limit=limit\n		)\n		\n	def get_monthly_stats(self):\n		\"\"\"Get monthly processing statistics\"\"\"\n		from frappe.utils import get_first_day, get_last_day\n		\n		start_date = get_first_day(today())\n		end_date = get_last_day(today())\n		\n		stats = frappe.db.sql(\"\"\"\n			SELECT \n				COUNT(*) as total_jobs,\n				SUM(CASE WHEN processing_status = 'Completed' THEN 1 ELSE 0 END) as successful,\n				SUM(CASE WHEN processing_status = 'Failed' THEN 1 ELSE 0 END) as failed,\n				AVG(processing_time) as avg_processing_time\n			FROM `tabProcessing Job`\n			WHERE customer = %s AND DATE(creation) BETWEEN %s AND %s\n		\"\"\", (self.name, start_date, end_date), as_dict=1)\n		\n		return stats[0] if stats else {\n			\"total_jobs\": 0, \"successful\": 0, \"failed\": 0, \"avg_processing_time\": 0\n		}\n		\n\n@frappe.whitelist()\ndef get_customer_dashboard_data(customer_name=None):\n	\"\"\"API endpoint for customer dashboard data\"\"\"\n	if not customer_name:\n		# Get customer by current user email\n		customer_name = frappe.db.get_value(\"SaaS Customer\", {\"email\": frappe.session.user}, \"name\")\n		\n	if not customer_name:\n		frappe.throw(\"Customer not found\")\n		\n	customer = frappe.get_doc(\"SaaS Customer\", customer_name)\n	\n	# Check permissions\n	if frappe.session.user != customer.email and not frappe.has_permission(\"SaaS Customer\", \"read\", customer_name):\n		frappe.throw(\"Not permitted\")\n		\n	return {\n		\"customer_info\": {\n			\"name\": customer.customer_name,\n			\"email\": customer.email,\n			\"subscription_plan\": customer.subscription_plan,\n			\"subscription_status\": customer.subscription_status,\n			\"trial_end_date\": customer.trial_end_date,\n			\"current_usage\": customer.current_usage,\n			\"usage_limit\": customer.usage_limit,\n			\"usage_percentage\": (customer.current_usage / customer.usage_limit * 100) if customer.usage_limit else 0\n		},\n		\"integration_status\": customer.get_integration_status(),\n		\"recent_jobs\": customer.get_recent_jobs(),\n		\"monthly_stats\": customer.get_monthly_stats()\n	}\n	\n\n@frappe.whitelist()\ndef check_quota_available(folder_id):\n	\"\"\"API endpoint for n8n to check if customer has quota available\"\"\"\n	# Get customer by drive folder\n	customer_name = frappe.db.get_value(\"Drive Integration\", {\"drive_folder_id\": folder_id}, \"customer\")\n	\n	if not customer_name:\n		return {\"quota_available\": False, \"error\": \"Customer not found\"}\n		\n	customer = frappe.get_doc(\"SaaS Customer\", customer_name)\n	\n	# Check subscription status\n	if customer.subscription_status not in [\"Active\", \"Trial\"]:\n		return {\"quota_available\": False, \"error\": \"Subscription inactive\"}\n		\n	# Check quota\n	quota_available = customer.current_usage < customer.usage_limit or customer.overage_allowed\n	\n	return {\n		\"quota_available\": quota_available,\n		\"current_usage\": customer.current_usage,\n		\"usage_limit\": customer.usage_limit,\n		\"customer_name\": customer.customer_name,\n		\"subscription_status\": customer.subscription_status\n	}"