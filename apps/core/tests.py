from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.inbound.models import Agent
from apps.inbound.models import Team


class CoreViewsTests(TestCase):
	def _create_user(self, username, password='testpass123', group_names=None):
		user = get_user_model().objects.create_user(username=username, password=password)

		for group_name in group_names or []:
			group, _ = Group.objects.get_or_create(name=group_name)
			user.groups.add(group)

		return user

	def test_home_redirects_anonymous_user_to_login(self):
		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('core:login'))

	def test_home_redirects_authenticated_user_to_dashboard(self):
		user = self._create_user('ana', group_names=['Assistentes'])
		team = Team.objects.create(name='Equipa Ana')
		agent = Agent.objects.create(team=team, name='Ana Assistente', user=user)
		self.client.force_login(user)

		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('dashboards:assistant_detail', args=[agent.id]))

	def test_home_renders_friendly_page_for_authenticated_user_without_dashboard_group(self):
		user = self._create_user('sem-acesso')
		self.client.force_login(user)

		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'core/no_dashboard_access.html')
		self.assertContains(response, 'Acesso ao dashboard pendente')

	def test_home_redirects_superuser_to_overview(self):
		user = get_user_model().objects.create_superuser(
			username='root-home',
			email='root-home@example.com',
			password='testpass123',
		)
		self.client.force_login(user)

		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('dashboards:overview'))

	def test_login_page_renders(self):
		response = self.client.get(reverse('core:login'))

		self.assertEqual(response.status_code, 200)

	def test_login_with_valid_credentials_authenticates_user(self):
		user = self._create_user('carla', group_names=['Supervisores'])

		response = self.client.post(
			reverse('core:login'),
			{'username': 'carla', 'password': 'testpass123'},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('dashboards:overview'))
		self.assertEqual(int(self.client.session['_auth_user_id']), user.pk)

	def test_login_assistant_with_linked_agent_redirects_to_own_dashboard(self):
		user = self._create_user('assist-link', group_names=['Assistentes'])
		team = Team.objects.create(name='Equipa Assist Link')
		agent = Agent.objects.create(team=team, name='Assist Link', user=user)

		response = self.client.post(
			reverse('core:login'),
			{'username': 'assist-link', 'password': 'testpass123'},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('dashboards:assistant_detail', args=[agent.id]))

	def test_login_with_invalid_credentials_does_not_authenticate_user(self):
		self._create_user('diana', group_names=['Assistentes'])

		response = self.client.post(
			reverse('core:login'),
			{'username': 'diana', 'password': 'credenciais-erradas'},
		)

		self.assertEqual(response.status_code, 200)
		self.assertNotIn('_auth_user_id', self.client.session)
		self.assertContains(response, 'Utilizador ou palavra-passe inválidos.')

	def test_logout_route_ends_session_and_protected_route_redirects_to_login(self):
		user = self._create_user('bruno', group_names=['Assistentes'])
		self.client.force_login(user)

		response = self.client.post(reverse('core:logout'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('core:login'))
		self.assertNotIn('_auth_user_id', self.client.session)

		protected_response = self.client.get(reverse('dashboards:overview'))
		self.assertEqual(protected_response.status_code, 302)
		self.assertIn(reverse('core:login'), protected_response.url)

	def test_anonymous_user_is_redirected_to_login_for_protected_dashboard_routes(self):
		routes = [
			reverse('dashboards:overview'),
			reverse('dashboards:services'),
			reverse('dashboards:assistants'),
			reverse('dashboards:monthly_rates'),
			reverse('dashboards:daily_rates'),
		]

		for route in routes:
			with self.subTest(route=route):
				response = self.client.get(route)
				self.assertEqual(response.status_code, 302)
				self.assertIn(reverse('core:login'), response.url)
