# coding: utf-8
import os
import time
import subprocess

from optparse import make_option

from django.core.management.base import BaseCommand

from dext.utils import pid

from game.workers.environment import workers_environment

class Command(BaseCommand):

    help = 'run game turns loop'

    requires_model_validation = False

    option_list = BaseCommand.option_list + ( make_option('-c', '--command',
                                                          action='store',
                                                          type=str,
                                                          dest='command',
                                                          help='start|stop|restart|status'),
                                              )

    @pid.protector('game_workers')
    def handle(self, *args, **options):

        command = options['command']

        if command == 'start':
            with open(os.devnull, 'w') as devnull:
                subprocess.Popen(['./manage.py', 'game_supervisor'], stdin=devnull, stdout=devnull, stderr=devnull)
                subprocess.Popen(['./manage.py', 'game_logic'], stdin=devnull, stdout=devnull, stderr=devnull)
                subprocess.Popen(['./manage.py', 'game_highlevel'], stdin=devnull, stdout=devnull, stderr=devnull)
                subprocess.Popen(['./manage.py', 'game_turns_loop'], stdin=devnull, stdout=devnull, stderr=devnull)
            print 'game started'

        elif command == 'stop':

            if pid.check('game_supervisor'):
                print 'supervisor found, send stop command'
                workers_environment.supervisor.cmd_stop()
                print 'waiting answer'
                answer_cmd = workers_environment.supervisor.stop_queue.get(block=True)
                answer_cmd.ack()
                print 'answer received'

            while (pid.check('game_supervisor') or
                   pid.check('game_logic') or
                   pid.check('game_highlevel') or
                   pid.check('game_turns_loop') ):
                time.sleep(0.1)

            print 'game stopped'

        elif command == 'restart':
            subprocess.call(['./manage.py', 'game_workers', 'stop'])
            subprocess.call(['./manage.py', 'game_workers', 'start'])
            print 'command "%s" does not implemented yet ' % command

        elif command == 'status':
            print 'command "%s" does not implemented yet ' % command