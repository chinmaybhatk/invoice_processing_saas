# Copyright (c) 2025, Your Company and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SubscriptionPlan(Document):
	def validate(self):
		"""Validate subscription plan data"""
		self.validate_pricing()
		self.calculate_annual_discount()
		
	def validate_pricing(self):
		"""Validate pricing logic"""
		if self.monthly_price <= 0:
			frappe.throw("Monthly price must be greater than 0")
			
		if self.annual_price and self.annual_price <= 0:
			frappe.throw("Annual price must be greater than 0")
			
		if self.processing_limit <= 0:
			frappe.throw("Processing limit must be greater than 0")
			
		if self.overage_rate and self.overage_rate < 0:
			frappe.throw("Overage rate cannot be negative")
			
	def calculate_annual_discount(self):
		"""Calculate annual discount percentage"""
		if self.annual_price and self.monthly_price:
			annual_equivalent = self.monthly_price * 12
			discount = annual_equivalent - self.annual_price
			self.annual_discount_percent = (discount / annual_equivalent) * 100
			
	def get_effective_price(self, billing_cycle="Monthly"):
		"""Get effective price based on billing cycle"""
		if billing_cycle == "Annual" and self.annual_price:
			return self.annual_price
		return self.monthly_price
		
	def get_plan_features_list(self):
		"""Get list of plan features for display"""
		features = []
		
		# Add processing limit
		features.append(f"{self.processing_limit:,} invoices per month")
		
		# Add file size limit
		if self.max_file_size_mb:
			features.append(f"Up to {self.max_file_size_mb}MB file size")
			
		# Add retention period
		if self.retention_days:
			features.append(f"{self.retention_days} days data retention")
			
		# Add concurrent processing
		if self.concurrent_processing:
			features.append(f"{self.concurrent_processing} concurrent processing")
			
		# Add boolean features
		if self.api_access:
			features.append("API Access")
			
		if self.priority_support:
			features.append("Priority Support")
			
		if self.custom_integrations:
			features.append("Custom Integrations")
			
		# Add custom features from table
		for feature in self.plan_features:
			if feature.included:
				feature_text = feature.feature_name
				if feature.limit_value:
					feature_text += f" ({feature.limit_value})"
				features.append(feature_text)
				
		return features
		
	def can_upgrade_to(self, target_plan_code):
		"""Check if this plan can upgrade to target plan"""
		target_plan = frappe.get_doc("Subscription Plan", target_plan_code)
		
		# Can upgrade if target plan has higher processing limit or price
		return (target_plan.processing_limit > self.processing_limit or 
				target_plan.monthly_price > self.monthly_price)
				
	def get_overage_cost(self, overage_count):
		"""Calculate overage cost"""
		if not self.overage_rate or overage_count <= 0:
			return 0
		return overage_count * self.overage_rate


# Child DocType for Plan Features
class SubscriptionPlanFeature(Document):
	pass


@frappe.whitelist()
def get_active_plans():
	"""Get all active subscription plans for signup form"""
	plans = frappe.get_all("Subscription Plan",
		filters={"is_active": 1},
		fields=["name", "plan_name", "plan_code", "monthly_price", "annual_price", 
				"processing_limit", "feature_highlight", "description", "trial_days"],
		order_by="sort_order asc"
	)
	
	# Add features list to each plan
	for plan in plans:
		plan_doc = frappe.get_doc("Subscription Plan", plan.name)
		plan["features"] = plan_doc.get_plan_features_list()
		plan["annual_discount_percent"] = plan_doc.annual_discount_percent
		
	return plans
	

@frappe.whitelist()
def get_plan_comparison():
	"""Get plan comparison data for pricing page"""
	plans = frappe.get_all("Subscription Plan",
		filters={"is_active": 1},
		order_by="sort_order asc"
	)
	
	comparison_data = []
	
	for plan_name in plans:
		plan = frappe.get_doc("Subscription Plan", plan_name.name)
		
		comparison_data.append({
			"plan_code": plan.plan_code,
			"plan_name": plan.plan_name,
			"monthly_price": plan.monthly_price,
			"annual_price": plan.annual_price,
			"annual_discount_percent": plan.annual_discount_percent,
			"processing_limit": plan.processing_limit,
			"feature_highlight": plan.feature_highlight,
			"features": plan.get_plan_features_list(),
			"api_access": plan.api_access,
			"priority_support": plan.priority_support,
			"custom_integrations": plan.custom_integrations,
			"max_file_size_mb": plan.max_file_size_mb,
			"retention_days": plan.retention_days,
			"trial_days": plan.trial_days
		})
		
	return comparison_data


@frappe.whitelist()
def calculate_upgrade_cost(current_plan, target_plan, billing_cycle="Monthly"):
	"""Calculate prorated upgrade cost"""
	current_doc = frappe.get_doc("Subscription Plan", current_plan)
	target_doc = frappe.get_doc("Subscription Plan", target_plan)
	
	current_price = current_doc.get_effective_price(billing_cycle)
	target_price = target_doc.get_effective_price(billing_cycle)
	
	# Simple calculation - can be enhanced with proration logic
	price_difference = target_price - current_price
	
	return {
		"current_plan": current_doc.plan_name,
		"target_plan": target_doc.plan_name,
		"current_price": current_price,
		"target_price": target_price,
		"price_difference": price_difference,
		"billing_cycle": billing_cycle
	}