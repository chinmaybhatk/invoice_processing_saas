app_name = "invoice_processing_saas"
app_title = "Invoice Processing SaaS"
app_publisher = "Your Company"
app_description = "SaaS Invoice Processing Automation with AI-powered extraction"
app_email = "admin@yourcompany.com"
app_license = "MIT"
app_version = "1.0.0"

# Required Frappe apps
required_apps = ["frappe"]

# Included in website sitemap
website_route_rules = [
	{"from_route": "/signup", "to_route": "saas-customer-signup"},
	{"from_route": "/dashboard", "to_route": "customer-dashboard"},
	{"from_route": "/integrations", "to_route": "customer-integrations"},
	{"from_route": "/billing", "to_route": "customer-billing"},
]

# Website context
website_context = {
	"favicon": "/assets/invoice_processing_saas/images/favicon.ico",
	"splash_image": "/assets/invoice_processing_saas/images/splash.png"
}

# Application setup hooks
after_install = "invoice_processing_saas.setup.after_install"
after_app_install = "invoice_processing_saas.setup.after_app_install"

# Document Events
doc_events = {
	"SaaS Customer": {
		"after_insert": "invoice_processing_saas.api.customer.after_customer_insert",
		"on_update": "invoice_processing_saas.api.customer.on_customer_update",
	},
	"Processing Job": {
		"after_insert": "invoice_processing_saas.api.processing.after_job_insert",
		"on_update": "invoice_processing_saas.api.processing.on_job_update",
	},
	"Usage Tracking": {
		"on_update": "invoice_processing_saas.api.usage.on_usage_update",
	}
}

# Scheduled Tasks
scheduler_events = {
	"cron": {
		"0 0 * * *": [  # Daily at midnight
			"invoice_processing_saas.tasks.daily.update_usage_tracking",
			"invoice_processing_saas.tasks.daily.check_subscription_renewals",
			"invoice_processing_saas.tasks.daily.cleanup_old_jobs"
		],
		"*/15 * * * *": [  # Every 15 minutes
			"invoice_processing_saas.tasks.frequent.check_integration_health",
			"invoice_processing_saas.tasks.frequent.process_pending_jobs"
		],
		"0 */6 * * *": [  # Every 6 hours
			"invoice_processing_saas.tasks.periodic.refresh_oauth_tokens",
			"invoice_processing_saas.tasks.periodic.generate_usage_reports"
		]
	},
	"daily": [
		"invoice_processing_saas.tasks.daily.send_usage_summaries",
		"invoice_processing_saas.tasks.daily.billing_reminders"
	],
	"weekly": [
		"invoice_processing_saas.tasks.weekly.generate_analytics_report"
	],
	"monthly": [
		"invoice_processing_saas.tasks.monthly.archive_old_data",
		"invoice_processing_saas.tasks.monthly.subscription_billing"
	]
}

# Override default error pages
error_pages = {
	"404": "/templates/errors/404.html",
	"500": "/templates/errors/500.html"
}

# Permissions
has_permission = {
	"SaaS Customer": "invoice_processing_saas.permissions.saas_customer_permission",
	"Processing Job": "invoice_processing_saas.permissions.processing_job_permission",
	"Drive Integration": "invoice_processing_saas.permissions.drive_integration_permission",
	"Accounting Integration": "invoice_processing_saas.permissions.accounting_integration_permission",
}

# Authentication
auth_hooks = [
	"invoice_processing_saas.auth.validate_auth_via_api_keys"
]

# Jinja environment
jenv = {
	"methods": [
		"invoice_processing_saas.utils.get_customer_info",
		"invoice_processing_saas.utils.get_subscription_status",
		"invoice_processing_saas.utils.format_currency"
	]
}

# Boot session
boot_session = "invoice_processing_saas.boot.boot_session"

# Website user (portal users)
portal_menu_items = [
	{
		"title": "Dashboard", 
		"route": "/dashboard", 
		"reference_doctype": "SaaS Customer",
		"role": "Customer"
	},
	{
		"title": "Processing Jobs", 
		"route": "/app/processing-job", 
		"reference_doctype": "Processing Job",
		"role": "Customer"
	},
	{
		"title": "Integrations", 
		"route": "/integrations", 
		"reference_doctype": "Drive Integration",
		"role": "Customer"
	},
	{
		"title": "Billing", 
		"route": "/billing", 
		"reference_doctype": "Subscription Plan",
		"role": "Customer"
	},
]

# Override standard methods
override_doctype_dashboards = {
	"Customer": "invoice_processing_saas.dashboard_overrides.customer_dashboard"
}

# Clear cache on specific events
doctype_js = {
	"Customer": "public/js/customer.js"
}

# API Rate limiting
api_call_limits = {
	"invoice_processing_saas.api.processing.create_job": {
		"limit": 100,  # 100 calls per hour
		"window": 3600
	},
	"invoice_processing_saas.api.processing.store_result": {
		"limit": 200,  # 200 calls per hour
		"window": 3600
	}
}

# Custom roles
standard_portal_menu_items = [
	{"title": "Personal Details", "route": "/app/user"},
	{"title": "Dashboard", "route": "/dashboard"},
	{"title": "Processing Jobs", "route": "/app/processing-job"},
	{"title": "Integrations", "route": "/integrations"},
	{"title": "Billing", "route": "/billing"},
]

# Email templates
email_brand_logo = "/assets/invoice_processing_saas/images/logo.png"

# Notification settings
sounds = [
	{"name": "processing-complete", "src": "/assets/invoice_processing_saas/sounds/success.mp3"},
	{"name": "processing-failed", "src": "/assets/invoice_processing_saas/sounds/error.mp3"}
]

# Custom fields
fixtures = [
	{
		"doctype": "Custom Field", 
		"filters": {"dt": ["in", ["Customer", "User"]]}
	},
	{
		"doctype": "Property Setter", 
		"filters": {"doc_type": ["in", ["Customer", "User"]]}
	},
	"Subscription Plan",
	"Invoice Processing Settings"
]

# Export fixtures
export_fixtures = True

# Translation 
translate_linked_doctypes = True