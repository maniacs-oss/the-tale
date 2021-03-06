# coding: utf-8
import time
import datetime

from unittest import mock

from django.test import client
from django.core.urlresolvers import reverse

from dext.common.utils import s11n

from the_tale.common.utils.testcase import TestCase

from the_tale.accounts.logic import login_page_url

from the_tale.game.logic import create_test_map, game_info_url, game_diary_url

from the_tale.game.pvp.models import BATTLE_1X1_STATE
from the_tale.game.pvp.tests.helpers import PvPTestsMixin

from the_tale.cms.news import logic as news_logic

from the_tale.game.heroes import logic as heroes_logic
from the_tale.game.heroes import messages as heroes_messages

from the_tale.game.prototypes import TimePrototype


class RequestTestsBase(TestCase, PvPTestsMixin):

    def setUp(self):
        super(RequestTestsBase, self).setUp()
        create_test_map()

        self.account_1 = self.accounts_factory.create_account()
        self.account_2 = self.accounts_factory.create_account()

        self.client = client.Client()

        self.game_info_url_1 = game_info_url(account_id=self.account_1.id)
        self.game_info_url_2 = game_info_url(account_id=self.account_2.id)
        self.game_info_url_no_id = game_info_url()

        self.request_login(self.account_1.email)


class GamePageRequestTests(RequestTestsBase):

    def test_game_page_unlogined(self):
        self.request_logout()
        self.check_redirect(reverse('game:'), login_page_url(reverse('game:')))

    def test_game_page_logined(self):
        response = self.client.get(reverse('game:'))
        self.assertEqual(response.status_code, 200)

    def test_game_page_when_pvp_in_queue(self):
        self.pvp_create_battle(self.account_1, self.account_2)
        self.pvp_create_battle(self.account_2, self.account_1)
        self.check_html_ok(self.client.get(reverse('game:')))

    def test_game_page_when_pvp_processing(self):
        self.pvp_create_battle(self.account_1, self.account_2, BATTLE_1X1_STATE.PROCESSING)
        self.pvp_create_battle(self.account_2, self.account_1, BATTLE_1X1_STATE.PROCESSING)
        self.check_redirect(reverse('game:'), reverse('game:pvp:'))


class InfoRequestTests(RequestTestsBase):

    def test_unlogined(self):
        self.request_logout()
        self.check_ajax_ok(self.request_ajax_json(self.game_info_url_1))

    def test_logined(self):
        response = self.client.get(self.game_info_url_1)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(s11n.from_json(response.content.decode('utf-8'))['data'].keys()), set(('turn', 'mode', 'map_version', 'account', 'enemy', 'game_state')))

    def test_no_id__logined(self):
        with mock.patch('the_tale.game.logic.form_game_info', mock.Mock(return_value={})) as form_game_info:
            self.check_ajax_ok(self.client.get(self.game_info_url_no_id))

        self.assertEqual(form_game_info.call_count, 1)
        self.assertEqual(form_game_info.call_args_list[0][1]['account'].id, self.account_1.id)

    def test_no_id__unlogined(self):
        self.request_logout()

        with mock.patch('the_tale.game.logic.form_game_info', mock.Mock(return_value={})) as form_game_info:
            self.check_ajax_ok(self.client.get(self.game_info_url_no_id))

        self.assertEqual(form_game_info.call_count, 1)
        self.assertEqual(form_game_info.call_args_list[0][1]['account'], None)

    def test_account_not_exists(self):
        response = self.request_ajax_json(game_info_url(account_id=666))
        self.check_ajax_error(response, 'account.wrong_value')

    def test_wrong_account_id(self):
        response = self.request_ajax_json(game_info_url(account_id='sdsd'))
        self.check_ajax_error(response, 'account.wrong_format')

    def test_client_turns(self):
        self.check_ajax_error(self.request_ajax_json(game_info_url(client_turns=['dds'])), 'client_turns.wrong_format')
        self.check_ajax_error(self.request_ajax_json(game_info_url(client_turns=['1', ''])), 'client_turns.wrong_format')
        self.check_ajax_ok(self.request_ajax_json(game_info_url(client_turns=['1'])))
        self.check_ajax_ok(self.request_ajax_json(game_info_url(client_turns=['1, 2, 3 ,4'])))
        self.check_ajax_ok(self.request_ajax_json(game_info_url(client_turns=[1, 2, 3 ,4])))
        self.check_ajax_ok(self.request_ajax_json(game_info_url(client_turns=['1',' 2',' 3 ','4'])))

    def test_client_turns_passed_to_data_receiver(self):
        with mock.patch('the_tale.game.heroes.objects.Hero.cached_ui_info_for_hero',
                        mock.Mock(return_value={'actual_on_turn': 666})) as cached_ui_info_for_hero:
            self.check_ajax_ok(self.request_ajax_json(game_info_url(client_turns=[1, 2, 3 ,4])))

        self.assertEqual(cached_ui_info_for_hero.call_args_list,
                         [mock.call(account_id=self.account_1.id,
                                    recache_if_required=True,
                                    patch_turns=[1, 2, 3, 4],
                                    for_last_turn=False)])



class NewsAlertsTests(TestCase):

    def setUp(self):
        super(NewsAlertsTests, self).setUp()
        create_test_map()
        self.client = client.Client()

        self.news = news_logic.create_news(caption='news-caption', description='news-description', content='news-content')

        self.account = self.accounts_factory.create_account()

        self.request_login(self.account.email)

    def check_reminder(self, url, caption, description, block):
        self.check_html_ok(self.client.get(url), texts=[('news-caption', caption),
                                                        ('news-description', description),
                                                        ('news-content', 0),
                                                        ('pgf-last-news-reminder', block)])

    def test_news_alert_for_new_account(self):
        self.check_reminder(reverse('game:'), 0, 0, 0)

    def test_news_alert(self):
        self.account.last_news_remind_time -= datetime.timedelta(seconds=666)
        self.account.save()

        self.check_reminder(reverse('game:'), 1, 1, 2)

    def test_no_news_alert(self):
        self.account.last_news_remind_time = datetime.datetime.now()
        self.account.save()
        self.check_reminder(reverse('game:'), 0, 0, 0)



class DiaryRequestTests(RequestTestsBase):

    def setUp(self):
        super(DiaryRequestTests, self).setUp()

        heroes_logic.push_message_to_diary(account_id=self.account_1.id, message=self.create_message(1), is_premium=False)
        heroes_logic.push_message_to_diary(account_id=self.account_1.id, message=self.create_message(2), is_premium=False)
        heroes_logic.push_message_to_diary(account_id=self.account_1.id, message=self.create_message(3), is_premium=False)


    def create_message(self, uid):
        return heroes_messages.MessageSurrogate(turn_number=TimePrototype.get_current_turn_number(),
                                                timestamp=time.time(),
                                                key=None,
                                                externals=None,
                                                message='message {}'.format(uid),
                                                position='position {}'.format(uid))



    def test_unlogined(self):
        self.request_logout()
        self.check_ajax_error(self.request_ajax_json(game_diary_url()), 'common.login_required')


    def test_logined(self):
        data = self.check_ajax_ok(self.request_ajax_json(game_diary_url()))

        self.assertIn('version', data)

        for message in data['messages']:
            self.assertEqual(set(message), {'timestamp',
                                            'game_time',
                                            'game_date',
                                            'message',
                                            'type',
                                            'variables',
                                            'position'})
