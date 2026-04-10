from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Team(models.Model):
	external_code = models.CharField(max_length=100, blank=True)
	name = models.CharField(max_length=120, unique=True)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['name']

	def __str__(self):
		return self.name


class Agent(models.Model):
	external_code = models.CharField(max_length=100, blank=True)
	name = models.CharField(max_length=120)
	team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='agents')
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name='agent_profile',
	)
	is_active = models.BooleanField(default=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['team__name', 'name']
		constraints = [
			models.UniqueConstraint(fields=['team', 'name'], name='unique_agent_name_per_team'),
		]

	def __str__(self):
		return f'{self.team.name} | {self.name}'


class OutcomeFinal(models.Model):
	code = models.SlugField(max_length=120, unique=True)
	label = models.CharField(max_length=120)
	is_call_drop_outcome = models.BooleanField(default=False)

	class Meta:
		ordering = ['label']

	def __str__(self):
		return self.label


class RetentionAction(models.Model):
	code = models.SlugField(max_length=120, unique=True)
	label = models.CharField(max_length=120)
	is_pending = models.BooleanField(default=False)

	class Meta:
		ordering = ['label']

	def __str__(self):
		return self.label


class ChurnReason(models.Model):
	code = models.SlugField(max_length=120, unique=True)
	label = models.CharField(max_length=120)
	category_group = models.CharField(max_length=120, blank=True)

	class Meta:
		ordering = ['label']

	def __str__(self):
		return self.label


class ServiceType(models.Model):
	code = models.SlugField(max_length=120, unique=True)
	label = models.CharField(max_length=120)

	class Meta:
		ordering = ['label']

	def __str__(self):
		return self.label


class Interaction(models.Model):
	class Direction(models.TextChoices):
		INBOUND = 'inbound', 'Inbound'
		OUTBOUND = 'outbound', 'Outbound'

	batch = models.ForeignKey('imports_app.ImportBatch', on_delete=models.PROTECT, related_name='interactions')
	direction = models.CharField(max_length=20, choices=Direction.choices, default=Direction.INBOUND)
	call_id_external = models.CharField(max_length=100, blank=True)
	team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='interactions')
	agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name='interactions')
	start_at = models.DateTimeField(db_index=True)
	end_at = models.DateTimeField(db_index=True)
	duration_seconds = models.PositiveIntegerField(default=0)
	occurred_on = models.DateField(db_index=True)
	final_outcome = models.ForeignKey(OutcomeFinal, on_delete=models.PROTECT, related_name='interactions')
	retention_action = models.ForeignKey(
		RetentionAction, on_delete=models.PROTECT, related_name='interactions'
	)
	churn_reason = models.ForeignKey(
		ChurnReason,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name='interactions',
	)
	service_type = models.ForeignKey(
		ServiceType,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name='interactions',
	)
	is_call_drop = models.BooleanField(default=False)
	category = models.CharField(max_length=200, blank=True)
	subcategory = models.CharField(max_length=200, blank=True)
	observations = models.TextField(blank=True)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-start_at']
		constraints = [
			models.CheckConstraint(
				condition=models.Q(end_at__gte=models.F('start_at')),
				name='interaction_end_after_start',
			),
		]
		indexes = [
			models.Index(fields=['direction', 'occurred_on']),
			models.Index(fields=['team', 'occurred_on']),
			models.Index(fields=['agent', 'occurred_on']),
		]

	def clean(self):
		if self.agent_id and self.team_id and self.agent.team_id != self.team_id:
			raise ValidationError('Agent must belong to the selected team.')

	def save(self, *args, **kwargs):
		if self.start_at and self.end_at:
			delta: timedelta = self.end_at - self.start_at
			self.duration_seconds = max(int(delta.total_seconds()), 0)
			self.occurred_on = self.start_at.date()
		super().save(*args, **kwargs)

	def __str__(self):
		return f'{self.agent.name} | {self.final_outcome.label} | {self.start_at:%Y-%m-%d %H:%M}'


class OutboundInteraction(models.Model):
	batch = models.ForeignKey('imports_app.ImportBatch', on_delete=models.PROTECT, related_name='outbound_interactions')
	call_id_external = models.CharField(max_length=100, blank=True)
	team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name='outbound_interactions')
	agent = models.ForeignKey(Agent, on_delete=models.PROTECT, related_name='outbound_interactions')
	start_at = models.DateTimeField(db_index=True)
	end_at = models.DateTimeField(db_index=True)
	duration_seconds = models.PositiveIntegerField(default=0)
	occurred_on = models.DateField(db_index=True)
	final_outcome = models.ForeignKey(OutcomeFinal, on_delete=models.PROTECT, related_name='outbound_interactions')
	retention_action = models.ForeignKey(
		RetentionAction, on_delete=models.PROTECT, related_name='outbound_interactions'
	)
	churn_reason = models.ForeignKey(
		ChurnReason,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name='outbound_interactions',
	)
	service_type = models.ForeignKey(
		ServiceType,
		on_delete=models.PROTECT,
		null=True,
		blank=True,
		related_name='outbound_interactions',
	)
	is_call_drop = models.BooleanField(default=False)
	category = models.CharField(max_length=200, blank=True)
	subcategory = models.CharField(max_length=200, blank=True)
	observations = models.TextField(blank=True)
	metadata = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-start_at']
		constraints = [
			models.CheckConstraint(
				condition=models.Q(end_at__gte=models.F('start_at')),
				name='outbound_interaction_end_after_start',
			),
		]
		indexes = [
			models.Index(fields=['occurred_on']),
			models.Index(fields=['category']),
		]

	def clean(self):
		if self.agent_id and self.team_id and self.agent.team_id != self.team_id:
			raise ValidationError('Agent must belong to the selected team.')

	def save(self, *args, **kwargs):
		if self.start_at and self.end_at:
			delta: timedelta = self.end_at - self.start_at
			self.duration_seconds = max(int(delta.total_seconds()), 0)
			self.occurred_on = self.start_at.date()
		super().save(*args, **kwargs)

	def __str__(self):
		return f'Outbound {self.call_id_external or self.id} @ {self.start_at:%Y-%m-%d %H:%M}'
