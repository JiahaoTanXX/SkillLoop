"""Exact-tokenizer transport lifetime and failure handling without a GPU."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from skillloop.runtime.gateway import ExactDockerTokenizer, GatewayError


FAKE_WORKER = """
import json,sys
for line in sys.stdin:
    p=json.loads(line)
    count=len(p['text']) if p['operation']=='text' else len(p['messages'])
    print(json.dumps({'id':p['id'],'count':count}),flush=True)
"""


class TokenizerWorkerTests(unittest.TestCase):
    def worker(self, code=FAKE_WORKER):
        original = subprocess.Popen
        def start(args, **kwargs):
            self.assertEqual(args[:4], ['docker', 'exec', '-i', 'isolated-role'])
            self.assertNotIn('sensitive input', args)
            return original([sys.executable, '-u', '-c', code], **kwargs)
        return patch('skillloop.runtime.gateway.subprocess.Popen', side_effect=start)

    def test_reuses_one_process_and_transports_unicode_newlines_via_stdin(self):
        with self.worker() as start, ExactDockerTokenizer('isolated-role') as tokenizer:
            self.assertEqual(tokenizer.count_text('sensitive input\n中文'), 18)
            self.assertEqual(tokenizer.count([{'role':'user','content':'sensitive input'}], [],
                enable_thinking=False), 1)
            self.assertEqual(tokenizer.count_text('sensitive input\n中文'), 18)
            self.assertEqual(start.call_count, 1)
            process = tokenizer._process
        self.assertIsNotNone(process.poll())
        self.assertTrue(process.stdout.closed)

    def test_separate_owners_never_share_process(self):
        with self.worker() as start:
            with ExactDockerTokenizer('isolated-role') as first, ExactDockerTokenizer('isolated-role') as second:
                self.assertEqual(first.count_text('same'), second.count_text('same'))
                self.assertIsNot(first._process, second._process)
            self.assertEqual(start.call_count, 2)

    def test_wrong_request_id_or_invalid_count_closes_process(self):
        for result in ({'id':0,'count':1}, {'id':1,'count':-1}, {'id':1,'count':True}, {'id':1,'count':'2'}):
            code = "import sys\nsys.stdin.readline()\nprint(" + repr(json.dumps(result)) + ",flush=True)\n"
            with self.subTest(result=result), self.worker(code), ExactDockerTokenizer('isolated-role') as tokenizer:
                with self.assertRaisesRegex(GatewayError, 'tokenizer_invalid_count'):
                    tokenizer.count_text('input')
                self.assertIsNone(tokenizer._process)

    def test_eof_and_timeout_fail_closed(self):
        with self.worker('import sys; sys.stdin.readline()'), ExactDockerTokenizer('isolated-role') as tokenizer:
            with self.assertRaises(GatewayError):
                tokenizer.count_text('input')
        with self.worker(), ExactDockerTokenizer('isolated-role') as tokenizer:
            with patch('skillloop.runtime.gateway.select.select', return_value=([], [], [])):
                with self.assertRaisesRegex(GatewayError, 'tokenizer_unavailable'):
                    tokenizer.count_text('input')
            self.assertIsNone(tokenizer._process)


if __name__ == '__main__':
    unittest.main()
