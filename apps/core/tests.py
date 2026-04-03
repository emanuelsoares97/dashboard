from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
	def test_home_redirects_to_dashboard_overview(self):
		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 302)
		self.assertEqual(response.url, reverse('dashboards:overview'))
