# coding: utf-8

from common.utils.testcase import TestCase

from accounts.prototypes import AccountPrototype
from accounts.logic import register_user

from game.logic import create_test_map

from game.ratings.models import RatingValues
from game.ratings.prototypes import RatingValuesPrototype

class PrototypeTestsBase(TestCase):

    def setUp(self):
        self.place1, self.place2, self.place3 = create_test_map()

        register_user('user_1', 'user_1@test.com', '111111')
        register_user('user_2', 'user_2@test.com', '111111')
        register_user('user_3', 'user_3@test.com', '111111')
        register_user('user_4', 'user_4@test.com', '111111')

        self.account_1 = AccountPrototype.get_by_nick('user_1')
        self.account_2 = AccountPrototype.get_by_nick('user_2')
        self.account_3 = AccountPrototype.get_by_nick('user_3')
        self.account_4 = AccountPrototype.get_by_nick('user_4')

class RatingPrototypeTests(PrototypeTestsBase):

    def setUp(self):
        super(RatingPrototypeTests, self).setUp()


    def test_initialize(self):
        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.account_id for rv in RatingValues.objects.all().order_by('account__id')],
                         [self.account_1.id, self.account_2.id, self.account_3.id, self.account_4.id, ])

    def test_fast_accounts_filtration(self):
        register_user('user_5')
        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.account_id for rv in RatingValues.objects.all().order_by('account__id')],
                         [self.account_1.id, self.account_2.id, self.account_3.id, self.account_4.id, ])

    def set_values(self, account, might=0, level=0, power=0):
        angel = account.angel
        angel.might = might
        angel.save()

        hero = angel.get_hero()
        hero.model.might = might
        hero.model.level = level
        hero.model.raw_power = power
        hero.model.save()

    def test_might(self):
        self.set_values(self.account_1, might=10)
        self.set_values(self.account_2, might=1)
        self.set_values(self.account_3, might=17)
        self.set_values(self.account_4, might=5)

        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.might for rv in RatingValues.objects.all().order_by('account__id')],
                         [10.0, 1.0, 17.0, 5.0 ])

    def create_bill(self, index, owner, state):
        from game.bills.bills import PlaceRenaming
        from game.bills.prototypes import BillPrototype

        bill_data = PlaceRenaming(place_id=self.place1.id, base_name='new_name_%d' % index)
        bill = BillPrototype.create(owner, 'bill-%d-caption' % index, 'bill-%d-rationale' % index, bill_data)
        bill.state = state
        bill.save()


    def test_bills_count(self):
        from forum.models import Category, SubCategory
        from game.bills.conf import bills_settings
        from game.bills.models import BILL_STATE

        forum_category = Category.objects.create(caption='category-1', slug='category-1')
        SubCategory.objects.create(caption=bills_settings.FORUM_CATEGORY_SLUG + '-caption',
                                   slug=bills_settings.FORUM_CATEGORY_SLUG,
                                   category=forum_category)

        self.create_bill(0, self.account_2, BILL_STATE.VOTING)
        self.create_bill(1, self.account_2, BILL_STATE.ACCEPTED)
        self.create_bill(2, self.account_2, BILL_STATE.REJECTED)

        self.create_bill(3, self.account_3, BILL_STATE.ACCEPTED)
        self.create_bill(4, self.account_3, BILL_STATE.ACCEPTED)
        self.create_bill(5, self.account_3, BILL_STATE.REJECTED)

        self.create_bill(6, self.account_1, BILL_STATE.REJECTED)
        self.create_bill(7, self.account_1, BILL_STATE.REJECTED)

        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.bills_count for rv in RatingValues.objects.all().order_by('account__id')],
                         [0, 1, 2, 0])

    def test_level(self):
        self.set_values(self.account_1, level=10)
        self.set_values(self.account_2, level=9)
        self.set_values(self.account_3, level=7)
        self.set_values(self.account_4, level=1)

        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.level for rv in RatingValues.objects.all().order_by('account__id')],
                         [10, 9, 7, 1 ])


    def test_power(self):
        self.set_values(self.account_1, power=9)
        self.set_values(self.account_2, power=10)
        self.set_values(self.account_3, power=7)
        self.set_values(self.account_4, power=1)

        RatingValuesPrototype.recalculate()
        self.assertEqual([rv.power for rv in RatingValues.objects.all().order_by('account__id')],
                         [9, 10, 7, 1 ])