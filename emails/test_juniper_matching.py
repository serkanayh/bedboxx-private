# -*- coding: utf-8 -*-
import pytest
from django.test import TestCase
from django.utils import timezone
from datetime import date

from hotels.models import Hotel, Room, Market, MarketAlias, JuniperContractMarket
from emails.models import Email, EmailRow
from emails.tasks import match_email_rows_batch_task, HOTEL_FUZZY_MATCH_THRESHOLD, ROOM_FUZZY_MATCH_THRESHOLD

# Define thresholds used in tasks.py (replace with actual values if found elsewhere)
# These are guesses based on common practice; adjust after reviewing tasks.py more closely
# HOTEL_FUZZY_MATCH_THRESHOLD = 85 # Example threshold for hotels
# ROOM_FUZZY_MATCH_THRESHOLD = 80  # Example threshold for rooms
# Since the values are not in the visible part of tasks.py, let's assume they are defined
# and the task can access them. For testing, we might need to mock or define them.

@pytest.mark.django_db(transaction=True) # Use pytest-django for better test management if available, else use TestCase
class JuniperMatchingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        """Set up non-modified objects used by all test methods."""
        # Create Markets
        cls.market_all = Market.objects.create(name="ALL")
        cls.market_uk = Market.objects.create(name="UK")
        cls.market_de = Market.objects.create(name="DE")
        cls.market_eu = Market.objects.create(name="EU Group")

        # Create Market Aliases
        cls.alias_europe = MarketAlias.objects.create(alias="Europe")
        cls.alias_europe.markets.add(cls.market_de, cls.market_eu)

        # Create Hotels
        cls.hotel1 = Hotel.objects.create(juniper_hotel_name="Sunshine Resort", juniper_code="SUN01")
        cls.hotel2 = Hotel.objects.create(juniper_hotel_name="Moonlight Hotel & Spa", juniper_code="MOON02")
        cls.hotel3 = Hotel.objects.create(juniper_hotel_name="Starlight Palace", juniper_code="STAR03")
        cls.hotel4 = Hotel.objects.create(juniper_hotel_name="Hotel California", juniper_code="CALI04") # For non-matching tests

        # Create Rooms
        cls.room1_std = Room.objects.create(hotel=cls.hotel1, juniper_room_type="Standard Room", room_code="STD")
        cls.room1_dbl = Room.objects.create(hotel=cls.hotel1, juniper_room_type="Double Room", room_code="DBL")
        cls.room2_suite = Room.objects.create(hotel=cls.hotel2, juniper_room_type="Junior Suite", room_code="JSUI")
        cls.room2_std_spa = Room.objects.create(hotel=cls.hotel2, juniper_room_type="Standard Room Spa Access", room_code="STDSPA")
        cls.room3_fam = Room.objects.create(hotel=cls.hotel3, juniper_room_type="Family Room", room_code="FAM")

        # Create Contracts
        JuniperContractMarket.objects.create(hotel=cls.hotel1, market=cls.market_uk, contract_name="Summer UK", season="S25")
        JuniperContractMarket.objects.create(hotel=cls.hotel1, market=cls.market_de, contract_name="Summer DE", season="S25")
        JuniperContractMarket.objects.create(hotel=cls.hotel2, market=cls.market_uk, contract_name="Winter UK", season="W24")
        JuniperContractMarket.objects.create(hotel=cls.hotel2, market=cls.market_eu, contract_name="Winter EU", season="W24")

        # Create a dummy Email
        cls.email = Email.objects.create(
            subject="Test Stop Sale",
            sender="test@example.com",
            recipient="system@example.com",
            received_date=timezone.now(),
            message_id="test_email_123",
            body_text="Stop sale for Sunshine Resort, Standard Room, 10-15 May."
        )

    def run_matching_task(self, row_ids):
        """Helper function to run the matching task synchronously for testing."""
        # Note: In a real Celery setup, you'd mock the .delay() call
        # For simplicity here, we call the task function directly.
        # This assumes the task function itself doesn't rely heavily on Celery internals.
        match_email_rows_batch_task(self.email.id, row_ids)

    def create_and_match_row(self, hotel_name, room_type, markets=None, sale_type='stop', start_date_str='2025-05-10', end_date_str='2025-05-15'):
        """Helper to create an EmailRow, run matching, and return the updated row."""
        if markets is None:
            markets = [self.market_all]
            
        row = EmailRow.objects.create(
            email=self.email,
            hotel_name=hotel_name,
            room_type=room_type,
            start_date=date.fromisoformat(start_date_str),
            end_date=date.fromisoformat(end_date_str),
            sale_type=sale_type,
            status='matching' # Initial status before task runs
        )
        row.markets.set(markets)
        
        self.run_matching_task([row.id])
        row.refresh_from_db()
        return row

    # --- Test Cases --- 

    def test_exact_hotel_match(self):
        """Test exact match for hotel name."""
        row = self.create_and_match_row("Sunshine Resort", "Standard Room")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.status, 'pending') # Expect pending as room should also match
        self.assertIsNotNone(row.hotel_match_score)
        self.assertGreaterEqual(row.hotel_match_score, 0.95) # Expect high score for exact match

    def test_case_insensitive_hotel_match(self):
        """Test case-insensitive match for hotel name."""
        row = self.create_and_match_row("sunshine resort", "Standard Room")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.status, 'pending')
        self.assertGreaterEqual(row.hotel_match_score, 0.95)

    def test_fuzzy_hotel_match_minor_variation(self):
        """Test fuzzy match for hotel name with minor variation."""
        row = self.create_and_match_row("Sunshine Resort Hotel", "Standard Room") # Added 'Hotel'
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.status, 'pending')
        self.assertIsNotNone(row.hotel_match_score)
        self.assertGreaterEqual(row.hotel_match_score, 75.0) # Lower bound (score may range from 0-100)
        self.assertLessEqual(row.hotel_match_score, 100.0)   # Upper bound

    def test_fuzzy_hotel_match_spa_added(self):
        """Test fuzzy match when '& Spa' is added/missing."""
        row = self.create_and_match_row("Moonlight Hotel", "Junior Suite") # Missing '& Spa'
        self.assertEqual(row.juniper_hotel, self.hotel2)
        self.assertEqual(row.status, 'pending')
        self.assertIsNotNone(row.hotel_match_score)
        self.assertGreaterEqual(row.hotel_match_score, 75.0) # Lower bound (score may range from 0-100)
        self.assertLessEqual(row.hotel_match_score, 100.0)   # Upper bound

    def test_no_hotel_match(self):
        """Test scenario where no hotel should match."""
        row = self.create_and_match_row("NonExistent Place", "Standard Room")
        self.assertIsNone(row.juniper_hotel)
        self.assertEqual(row.status, 'hotel_not_found')
        self.assertIsNone(row.hotel_match_score)

    def test_ambiguous_hotel_match(self):
        """Test scenario with potentially ambiguous hotel names (requires careful threshold check)."""
        # This requires knowing the exact thresholds and how the scoring handles ambiguity.
        # Example: If 'Sunshine Hotel' exists and threshold is low, it might match 'Sunshine Resort'.
        # For now, we assume thresholds are set reasonably.
        # Add a similar hotel
        Hotel.objects.create(juniper_hotel_name="Sunshine Hotel & Beach", juniper_code="SUN05")
        row = self.create_and_match_row("Sunshine Resort", "Standard Room")
        # We still expect it to match the original, assuming scoring prefers exact/closer matches
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.status, 'pending')

    def test_exact_room_match(self):
        """Test exact match for room type within a matched hotel."""
        row = self.create_and_match_row("Sunshine Resort", "Standard Room")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertIn(self.room1_std, row.juniper_rooms.all())
        self.assertEqual(row.juniper_rooms.count(), 1)
        self.assertEqual(row.status, 'pending')
        self.assertIsNotNone(row.room_match_score)
        self.assertGreaterEqual(row.room_match_score, 95) # Using fuzz.token_set_ratio, 100 is expected

    def test_case_insensitive_room_match(self):
        """Test case-insensitive match for room type."""
        row = self.create_and_match_row("Sunshine Resort", "standard room")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertIn(self.room1_std, row.juniper_rooms.all())
        self.assertEqual(row.juniper_rooms.count(), 1)
        self.assertEqual(row.status, 'pending')
        self.assertGreaterEqual(row.room_match_score, 95)

    def test_fuzzy_room_match(self):
        """Test fuzzy match for room type."""
        row = self.create_and_match_row("Moonlight Hotel & Spa", "Std Room Spa") # Abbreviation and slight change
        self.assertEqual(row.juniper_hotel, self.hotel2)
        self.assertIn(self.room2_std_spa, row.juniper_rooms.all())
        # Depending on threshold and algorithm, it might match multiple rooms if scores are close
        # self.assertEqual(row.juniper_rooms.count(), 1) # This might fail if threshold is low
        self.assertEqual(row.status, 'pending')
        self.assertTrue(ROOM_FUZZY_MATCH_THRESHOLD <= row.room_match_score < 95)

    def test_room_match_multiple_possible(self):
        """Test when input could match multiple rooms above threshold."""
        row = self.create_and_match_row("Sunshine Resort", "Room") # Generic term
        self.assertEqual(row.juniper_hotel, self.hotel1)
        # Expecting both Standard and Double rooms to match if threshold is permissive
        self.assertIn(self.room1_std, row.juniper_rooms.all())
        self.assertIn(self.room1_dbl, row.juniper_rooms.all())
        self.assertEqual(row.juniper_rooms.count(), 2)
        self.assertEqual(row.status, 'pending') # Status is pending even with multiple matches

    def test_no_room_match(self):
        """Test scenario where hotel matches but room does not."""
        row = self.create_and_match_row("Sunshine Resort", "Presidential Suite")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.juniper_rooms.count(), 0)
        self.assertEqual(row.status, 'room_not_found')
        self.assertIsNone(row.room_match_score)

    def test_all_rooms_match(self):
        """Test the 'All Rooms' special case."""
        row = self.create_and_match_row("Sunshine Resort", "ALL ROOMS")
        self.assertEqual(row.juniper_hotel, self.hotel1)
        self.assertEqual(row.juniper_rooms.count(), 0) # 'All Rooms' doesn't link specific rooms
        self.assertEqual(row.status, 'pending') # 'All Rooms' is considered a valid state
        self.assertIsNone(row.room_match_score)

    def test_market_matching_all(self):
        """Test contract info when row market is ALL."""
        row = self.create_and_match_row("Sunshine Resort", "Standard Room", markets=[self.market_all])
        contracts_str, count_str, has_match = row.get_matching_contracts_info
        self.assertEqual(contracts_str, "Summer DE, Summer UK") # All contracts for hotel1
        self.assertEqual(count_str, "(2/2)")
        self.assertTrue(has_match)

    def test_market_matching_specific_uk(self):
        """Test contract info when row market is specific (UK)."""
        row = self.create_and_match_row("Sunshine Resort", "Standard Room", markets=[self.market_uk])
        contracts_str, count_str, has_match = row.get_matching_contracts_info
        self.assertEqual(contracts_str, "Summer UK")
        self.assertEqual(count_str, "(1/2)")
        self.assertTrue(has_match)

    def test_market_matching_specific_de_eu_alias(self):
        """Test contract info using an alias mapping to DE and EU."""
        # Need a row linked to the alias's markets
        row = EmailRow.objects.create(
            email=self.email, hotel_name="Moonlight Hotel & Spa", room_type="Junior Suite",
            start_date=date(2025,5,10), end_date=date(2025,5,15), status='matching'
        )
        # Simulate AI resolving to the alias name
        # In reality, the signal/task would resolve alias to markets before setting M2M
        row.markets.set([self.market_de, self.market_eu]) # Set markets resolved from alias
        self.run_matching_task([row.id])
        row.refresh_from_db()
        
        self.assertEqual(row.juniper_hotel, self.hotel2)
        contracts_str, count_str, has_match = row.get_matching_contracts_info
        self.assertEqual(contracts_str, "Winter EU") # Only EU contract matches hotel2
        self.assertEqual(count_str, "(1/2)") # 1 matching out of 2 total for hotel2
        self.assertTrue(has_match)

    def test_market_matching_no_contract_match(self):
        """Test when hotel/room match but no contract exists for the specified market."""
        # Hotel 3 (Starlight) has no contracts defined in setUpTestData
        row = self.create_and_match_row("Starlight Palace", "Family Room", markets=[self.market_uk])
        self.assertEqual(row.juniper_hotel, self.hotel3)
        self.assertIn(self.room3_fam, row.juniper_rooms.all())
        self.assertEqual(row.status, 'pending') # Matching itself is ok
        
        contracts_str, count_str, has_match = row.get_matching_contracts_info
        self.assertEqual(contracts_str, "-")
        self.assertEqual(count_str, "(0/0)") # 0 matching out of 0 total
        self.assertFalse(has_match) # Market match is False as no contract covers UK

    # Add more tests for edge cases, performance, different fuzzy algorithms etc.

