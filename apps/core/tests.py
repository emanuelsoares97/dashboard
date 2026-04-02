from django.test import TestCase
from django.urls import reverse


class CoreViewsTests(TestCase):
	def test_home_returns_200_with_expected_template(self):
		response = self.client.get(reverse('core:home'))

		self.assertEqual(response.status_code, 200)
		self.assertTemplateUsed(response, 'core/home.html')
