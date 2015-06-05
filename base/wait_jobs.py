#!/usr/bin/env python
# -*- coding: utf-8 -*-

#req:
#end req

import os
import uuid
from datetime import datetime
import json
import hashlib

import poliglo
from poliglo.utils import to_json

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_NAME = 'wait_jobs'

def check_if_waiting_is_done(connection, script_id, process_id, waiting_workers_ids):
    total_jobs_keys = [
        poliglo.REDIS_KEY_INSTANCE_WORKER_JOBS % (
            script_id, process_id, wait_jobs_from, 'total'
        )
        for wait_jobs_from in waiting_workers_ids
    ]

    done_jobs_keys = [
        poliglo.REDIS_KEY_INSTANCE_WORKER_JOBS % (
            script_id, process_id, wait_jobs_from, 'done'
        )
        for wait_jobs_from in waiting_workers_ids
    ]

    pipe = connection.pipeline()
    temp_union = 'temp:%s:%s' % (datetime.now().isoformat().split('T')[0], str(uuid.uuid4()))
    pipe.sunionstore(temp_union, *total_jobs_keys)

    temp_diff = 'temp:%s:%s' % (datetime.now().isoformat().split('T')[0], str(uuid.uuid4()))
    pipe.sdiffstore(temp_diff, temp_union, *done_jobs_keys)
    pipe.delete(temp_diff)
    pipe.delete(temp_union)
    execute_result = pipe.execute()
    diff_count = execute_result[1]
    done_signature = hashlib.sha1(script_id+"_"+process_id+"_".join([str(x) for x in execute_result])).hexdigest()

    if  diff_count == 0:
        return (True, done_signature)
    return (False, done_signature)

def get_waiting_queue_name(process_id, worker_id, wait_jobs_from):
    wait_jobs_from_text = "_".join(sorted(list(set(wait_jobs_from))))
    return "wait_jobs:%s_%s_%s" % (
        process_id,
        worker_id,
        wait_jobs_from_text
    )

def process(specific_info, data, *args):
    inputs = poliglo.get_inputs(data, specific_info)
    connection = args[0].get('connection')

    waiting_queue_name = get_waiting_queue_name(
        data['process']['id'], data['process']['worker_id'], inputs['wait_jobs_from']
    )
    connection.lpush(waiting_queue_name, to_json(data))
    return []

def get_waiting_workers(worker_scripts):
    all_waiting_workers = []
    scripts_workers_waiting = {}
    for script_id, script_values in worker_scripts.iteritems():
        if not scripts_workers_waiting.get(script_id):
            scripts_workers_waiting[script_id] = {}
        for worker_id, worker_values in script_values.iteritems():
            if not scripts_workers_waiting[script_id].get(worker_id):
                scripts_workers_waiting[script_id][worker_id] = [worker_id,]
            for worker_id2 in worker_values.get('default_inputs', {}).get('wait_jobs_from', []):
                scripts_workers_waiting[script_id][worker_id].append(worker_id2)
                all_waiting_workers.append(worker_id2)
    return scripts_workers_waiting, list(set(all_waiting_workers))

def wait_is_done(connection, worker_scripts, script_id, process_id, process_name, worker_id, waiting_workers_ids):
    waiting_queue_name = get_waiting_queue_name(
        process_id, worker_id, waiting_workers_ids
    )
    worker = worker_scripts.get(script_id, {}).get(worker_id, {})
    for i, output_worker_id in enumerate(worker.get('outputs', [])):
        output_worker_type = worker.get('__outputs_types', [])[i]
        data = {'__read_from_queue': waiting_queue_name}
        poliglo.start_process(
            connection, script_id, output_worker_type,
            output_worker_id, process_name, data
        )

def main():
    worker_scripts, connection = poliglo.prepare_worker(POLIGLO_SERVER_URL, WORKER_NAME)
    script_waiting_workers, all_waiting_workers = get_waiting_workers(worker_scripts)
    # TODO: Move to redis
    already_done_signatures = []
    found_finalized = False
    found_wait = False
    timeout_wait = 1
    timeout_finalized = 1
    while True:
        if not found_wait:
            queue_message = connection.brpop(
                [poliglo.REDIS_KEY_QUEUE_FINALIZED,], timeout_finalized
            )
        if queue_message is not None:
            found_finalized = True
            finalized_data = json.loads(queue_message[1])
            if finalized_data['worker_id'] not in all_waiting_workers:
                continue
            script_id = finalized_data['process_type']
            process_id = finalized_data['process_id']
            process_name = finalized_data['process_name']
            for worker_id, waiting_workers_ids in script_waiting_workers[script_id].iteritems():
                status_done, done_signature = check_if_waiting_is_done(
                    connection, script_id, process_id, waiting_workers_ids
                )
                if status_done:
                    if done_signature not in already_done_signatures:
                        already_done_signatures.append(done_signature)
                        wait_is_done(
                            connection, worker_scripts, script_id, process_id,
                            process_name, worker_id, waiting_workers_ids
                        )
        else:
            found_finalized = False
        if not found_finalized:
            queue_message = connection.brpop([poliglo.REDIS_KEY_QUEUE % WORKER_NAME,], timeout_wait)
            if queue_message is not None:
                poliglo.default_main_inside(
                    connection, worker_scripts, queue_message, process, {'connection': connection}
                )
                found_wait = True
            else:
                found_wait = False
        queue_message = None




if __name__ == '__main__':
    main()












# INTEGRATION TEST
import signal
import subprocess
from unittest import TestCase
from shutil import copyfile
from time import sleep

from poliglo import start_process

class TestWaitJobs(TestCase):
    @classmethod
    def _setup_config(cls):
        cls.config = {
            "all": {
                "REDIS_HOST": "127.0.0.1",
                "REDIS_PORT": 6379,
                "REDIS_DB": 5,
                "POLIGLO_SERVER_URL": "http://localhost:9016"
            }
        }
        cls.config_path = "/tmp/config.json"
        open(cls.config_path, 'w').write(to_json(cls.config))

    @classmethod
    def _setup_script(cls):
        script = {
            "id": "test_wait_jobs",
            "name": "test_wait_jobs",
            "start_worker_id": "generate_numbers_1",
            "workers": [
                {
                    "worker_type": "generate_numbers",
                    "id": "generate_numbers_1",
                    "default_inputs": {
                        "numbers_range": [0, 10],
                        "sleep": 0
                    },
                    "outputs": ["filter_1"]
                },
                {
                    "worker_type": "filter",
                    "id": "filter_1",
                    "default_inputs": {
                        "min": 1000
                    },
                    "outputs": ["wait_jobs_1"]
                },
                {
                    "worker_type": "wait_jobs",
                    "id": "wait_jobs_1",
                    "default_inputs": {
                        "wait_jobs_from": ["generate_numbers_1", "filter_1", "wait_jobs_1"]
                    },
                    "outputs": ["count_numbers_1"]
                },
                {
                    "id": "count_numbers_1",
                    "worker_type": "count_numbers",
                    "outputs": []
                }
            ]
        }

        cls.script_path = "/tmp/wait_jobs_test_scripts"
        if not os.path.exists(cls.script_path):
            os.makedirs(cls.script_path)
        open(cls.script_path+"/script_test_wait_jobs.json", 'w').write(to_json(script))


    @classmethod
    def _setup_master_mind_server(cls):
        cls._setup_config()
        cls._setup_script()

        isolated_env = os.environ.copy()
        isolated_env['CONFIG_PATH'] = cls.config_path
        isolated_env['SCRIPTS_PATH'] = cls.script_path
        isolated_env['POLIGLO_SERVER_PORT'] = "9016"

        cmd = ["poliglo_server",]
        cls.server_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, shell=False, env=isolated_env, preexec_fn=os.setsid
        )

    @classmethod
    def _setup_workers_files(cls):
        cls.workers_path = "/tmp/wait_jobs_test_workers"
        if not os.path.exists(cls.workers_path):
            os.makedirs(cls.workers_path)

        #WORKER generate_numbers
        open(cls.workers_path+"/generate_numbers.py", 'w').write("""import time
import poliglo
import os

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_NAME = 'generate_numbers'

def process(specific_info, data, *args):
    inputs = poliglo.get_inputs(data, specific_info)
    numbers_range = inputs.get('numbers_range')
    sleep_time = inputs.get('sleep')

    for i in range(numbers_range[0], numbers_range[1]):
        time.sleep(sleep_time)
        yield {'number': i}

poliglo.default_main(POLIGLO_SERVER_URL, WORKER_NAME, process)
""")

        #WORKER filter
        open(cls.workers_path+"/filter.py", 'w').write("""import time
import poliglo
import os

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_NAME = 'filter'

def process(specific_info, data, *args):
    inputs = poliglo.get_inputs(data, specific_info)
    min_value = inputs.get("min")
    if inputs['number'] < min_value:
        return [inputs,]
    return []

poliglo.default_main(POLIGLO_SERVER_URL, WORKER_NAME, process)
""")

        #WORKER wait_jobs
        copyfile(os.path.abspath(__file__), cls.workers_path+'/wait_jobs.py')

        #WORKER count_numbers
        open(cls.workers_path+"/count_numbers.py", 'w').write("""import time
import poliglo
import os

POLIGLO_SERVER_URL = os.environ.get('POLIGLO_SERVER_URL')
WORKER_NAME = 'count_numbers'

def process(specific_info, data, *args):
    connection = args[0].get('connection')

    inputs = poliglo.get_inputs(data, specific_info)
    queue = inputs.get('__read_from_queue')

    total = 0
    while True:
        queue_data = connection.lpop(queue)
        if queue_data is None:
            break
        total +=1
    return [{'total': total}]

config = poliglo.get_config(POLIGLO_SERVER_URL, 'all')
connection = poliglo.get_connection(config)
poliglo.default_main(POLIGLO_SERVER_URL, WORKER_NAME, process, {'connection': connection})
""")

    @classmethod
    def _setup_workers(cls):
        cls._setup_workers_files()
        isolated_env = os.environ.copy()
        isolated_env['WORKERS_PATHS'] = cls.workers_path
        isolated_env['POLIGLO_SERVER_URL'] = POLIGLO_SERVER_URL
        project_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                '..'
            )
        )
        start_workers_path = os.path.join(project_dir, "start_workers.sh")

        cmd = [
            "/bin/bash",
            start_workers_path
        ]
        cls.workers_process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, shell=False, env=isolated_env, preexec_fn=os.setsid
        )

    @classmethod
    def setUpClass(cls):
        cls._setup_master_mind_server()
        sleep(1)
        cls._setup_workers()

    def setUp(self):
        self.connection = poliglo.get_connection(self.config.get('all'))
        self.connection.flushall()

    @classmethod
    def tearDownClass(cls):
        os.killpg(cls.server_process.pid, signal.SIGTERM)
        os.killpg(cls.workers_process.pid, signal.SIGTERM)

    def test_wait_for_all_jobs(self):
        self.process_id = start_process(
            self.connection,
            'test_wait_jobs', 'generate_numbers', 'generate_numbers_1', 'instance1', {}
        )
        queues = [None]
        while len(queues) > 0:
            sleep(1)
            queues = self.connection.keys("queue:*")
        total_finalized = self.connection.zcard(
            "scripts:test_wait_jobs:processes:%s:workers:count_numbers_1:finalized" % \
            self.process_id
        )
        self.assertEqual(1, total_finalized)

    def test_last_message_are_filtered(self):
        self.process_id = start_process(
            self.connection, 'test_wait_jobs',
            'generate_numbers', 'generate_numbers_1', 'instance1', {
                'numbers_range': [995, 1005]
            }
        )
        queues = [None]
        while len(queues) > 0:
            sleep(1)
            queues = self.connection.keys("queue:*")
        total_finalized = self.connection.zcard(
            "scripts:test_wait_jobs:processes:%s:workers:count_numbers_1:finalized" % \
            self.process_id
        )
        self.assertEqual(1, total_finalized)
