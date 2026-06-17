from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from .models import Area, Building, Unit, AssistantMessage, CachedPlace, SavedProperty


class RentalPrototypeTests(TestCase):
    def setUp(self):
        self.caretaker = User.objects.create_user(username='caretaker', password='pass12345')
        self.caretaker.profile.role = Profile.CARETAKER
        self.caretaker.profile.approval_status = Profile.APPROVED
        self.caretaker.profile.phone_verified = True
        self.caretaker.profile.save()
        self.area = Area.objects.create(name='Roysambu', slug='roysambu', latitude=-1.218, longitude=36.887)
        self.building = Building.objects.create(
            caretaker=self.caretaker,
            area=self.area,
            name='Sunrise Court',
            slug='sunrise-court',
            landmark='Near TRM',
            latitude=-1.218650,
            longitude=36.886180,
            is_published=True,
        )
        self.unit = Unit.objects.create(building=self.building, unit_type='bedsitter', rent=8500, deposit=8500, status=Unit.AVAILABLE)

    def test_markers_api_returns_available_building(self):
        response = self.client.get(reverse('building_markers_api'), {'area': 'roysambu', 'max_rent': '10000'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['buildings'][0]['name'], 'Sunrise Court')


    def test_location_search_returns_distance_sorted_results(self):
        response = self.client.get(reverse('building_markers_api'), {
            'lat': '-1.218600',
            'lng': '36.886100',
            'radius_km': '2',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['buildings'][0]['name'], 'Sunrise Court')
        self.assertEqual(payload['buildings'][0]['match_group'], 'exact')
        self.assertIn('verified', payload['message'].lower())

    def test_location_search_empty_result_is_honest(self):
        response = self.client.get(reverse('building_markers_api'), {
            'lat': '-1.500000',
            'lng': '37.200000',
            'radius_km': '1',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['buildings'], [])
        self.assertIn('No verified available units', payload['message'])


    def test_geocode_uses_rentwise_area_before_external_api(self):
        response = self.client.get(reverse('geocode_place_api'), {'q': 'Roysambu'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['result']['source'], 'rentwise_area')
        self.assertAlmostEqual(payload['result']['lat'], float(self.area.latitude), places=3)

    def test_place_suggestions_include_saved_building_or_area(self):
        response = self.client.get(reverse('place_suggestions_api'), {'q': 'TRM'})
        self.assertEqual(response.status_code, 200)
        labels = [item['label'] for item in response.json()['results']]
        self.assertTrue(any('Sunrise Court' in label for label in labels))

    def test_guest_assistant_saves_session_messages(self):
        response = self.client.post(reverse('assistant'), {'message': 'Find a bedsitter in Roysambu under 10000'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(AssistantMessage.objects.count(), 2)


    def test_assistant_no_listing_gives_honest_area_answer(self):
        from .assistant import answer_question
        reply = answer_question('I need help finding a house in Kahawa Wendani')
        self.assertIn('Kahawa', reply)
        self.assertIn('No verified available unit', reply)
        self.assertIn('walk around', reply.lower())

    def test_assistant_greeting_is_not_empty(self):
        from .assistant import answer_question
        reply = answer_question('hello')
        self.assertIn('Tell me the area', reply)
        self.assertIn('verified RentWise listings', reply)


    def test_assistant_advice_question_does_not_dump_listings(self):
        from .assistant import answer_question
        reply = answer_question('Apart from the houses in the database, what characteristic should I look for in a house?')
        self.assertIn('water availability', reply.lower())
        self.assertIn('security', reply.lower())
        self.assertNotIn('Sunrise Court', reply)

    def test_assistant_listing_question_still_returns_units(self):
        from .assistant import answer_question
        reply = answer_question('Find a bedsitter in Roysambu under 10000')
        self.assertIn('Sunrise Court', reply)
        self.assertIn('KSh 8,500', reply)



    def test_assistant_general_question_does_not_force_rental_advice_or_listings(self):
        from .assistant import answer_question
        reply = answer_question('what is the best color?')
        self.assertIn('color', reply.lower())
        self.assertNotIn('Sunrise Court', reply)
        self.assertNotIn('water availability', reply.lower())

    def test_assistant_returns_to_houses_when_user_asks_for_listing(self):
        from .assistant import answer_question
        reply = answer_question('Okay, now find a bedsitter in Roysambu under 10000')
        self.assertIn('Sunrise Court', reply)
        self.assertIn('KSh 8,500', reply)

    def test_signup_creates_caretaker_profile(self):
        response = self.client.post(reverse('signup'), {
            'username': 'denis',
            'email': 'denis@example.com',
            'phone': '0700000000',
            'password1': 'StrongPass12345',
            'password2': 'StrongPass12345',
        })
        self.assertEqual(response.status_code, 302)
        profile = User.objects.get(username='denis').profile
        self.assertEqual(profile.role, Profile.CARETAKER)
        self.assertEqual(profile.approval_status, Profile.PENDING)
        self.assertFalse(profile.phone_verified)


    def test_pending_caretaker_listing_is_not_public(self):
        pending = User.objects.create_user(username='pendingcare', password='pass12345')
        pending.profile.role = Profile.CARETAKER
        pending.profile.approval_status = Profile.PENDING
        pending.profile.phone_verified = False
        pending.profile.save()
        building = Building.objects.create(
            caretaker=pending,
            area=self.area,
            name='Hidden Court',
            slug='hidden-court',
            landmark='Hidden',
            latitude=-1.218700,
            longitude=36.886300,
            is_published=True,
        )
        Unit.objects.create(building=building, unit_type='bedsitter', rent=7000, deposit=7000, status=Unit.AVAILABLE)
        response = self.client.get(reverse('building_markers_api'), {'area': 'roysambu'})
        names = [item['name'] for item in response.json()['buildings']]
        self.assertIn('Sunrise Court', names)
        self.assertNotIn('Hidden Court', names)

    def test_caretaker_can_view_dashboard(self):
        self.client.login(username='caretaker', password='pass12345')
        response = self.client.get(reverse('caretaker_dashboard'))
        self.assertContains(response, 'Sunrise Court')

    def test_house_seeker_can_bookmark_and_remove_unit(self):
        seeker = User.objects.create_user(username='seeker', password='pass12345')
        seeker.profile.role = Profile.SEEKER
        seeker.profile.approval_status = Profile.APPROVED
        seeker.profile.save()
        self.client.login(username='seeker', password='pass12345')
        save_response = self.client.post(reverse('save_unit', args=[self.unit.id]), {'next': reverse('seeker_dashboard')})
        self.assertEqual(save_response.status_code, 302)
        self.assertEqual(seeker.saved_properties.count(), 1)
        self.assertEqual(SavedProperty.objects.get(user=seeker).unit, self.unit)
        dashboard = self.client.get(reverse('seeker_dashboard'))
        self.assertContains(dashboard, 'Sunrise Court')
        self.assertContains(dashboard, 'Bedsitter')
        remove_response = self.client.post(reverse('unsave_unit', args=[self.unit.id]), {'next': reverse('seeker_dashboard')})
        self.assertEqual(remove_response.status_code, 302)
        self.assertEqual(seeker.saved_properties.count(), 0)
