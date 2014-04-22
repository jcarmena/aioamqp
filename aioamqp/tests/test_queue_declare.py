import unittest

import asyncio

from . import testcase
from .. import exceptions


class QueueDeclareTestCase(testcase.RabbitTestCase, unittest.TestCase):

    _multiprocess_can_split_ = True

    @asyncio.coroutine
    def _test_queue_declare(self, queue_name, exclusive=False, durable=False, auto_delete=False):
        full_queue_name = self.full_queue_name(queue_name)

        # declare queue
        frame = yield from self.queue_declare(
            queue_name, no_wait=False, exclusive=exclusive, durable=durable,
            auto_delete=auto_delete, timeout=self.RABBIT_TIMEOUT)

        # assert returned frame has the good arguments
        self.assertEqual(full_queue_name, frame.arguments['queue'])

        # retrieve queue info from rabbitmqctl
        queues = yield from self.list_queues()
        queue = queues[full_queue_name]

        # assert queue has been declared witht the good arguments
        self.assertEqual(full_queue_name, queue['name'])
        self.assertEqual(0, queue['consumers'])
        self.assertEqual(0, queue['messages_ready'])
        self.assertEqual(auto_delete, queue['auto_delete'])
        self.assertEqual(durable, queue['durable'])

        # delete queue
        yield from self.safe_queue_delete(queue_name)

    def test_durable_and_auto_deleted(self):
        self.loop.run_until_complete(
            self._test_queue_declare('q', exclusive=False, durable=True, auto_delete=True))

    def test_durable_and_not_auto_deleted(self):
        self.loop.run_until_complete(
            self._test_queue_declare('q', exclusive=False, durable=True, auto_delete=False))

    def test_not_durable_and_auto_deleted(self):
        self.loop.run_until_complete(
            self._test_queue_declare('q', exclusive=False, durable=False, auto_delete=True))

    def test_not_durable_and_not_auto_deleted(self):
        self.loop.run_until_complete(
            self._test_queue_declare('q', exclusive=False, durable=False, auto_delete=False))

    def test_exclusive(self):
        @asyncio.coroutine
        def go():
            # create an exclusive queue
            yield from self.queue_declare("q", exclusive=True)
            queue_name = self.full_queue_name("q")
            # consume it
            yield from self.channel.basic_consume(queue_name, no_wait=False, timeout=self.RABBIT_TIMEOUT)
            # create an other amqp connection
            amqp2 = yield from self.create_amqp()
            channel = yield from self.create_channel(amqp=amqp2)
            # assert that this connection cannot connect to the queue
            with self.assertRaises(exceptions.ChannelClosed):
                yield from channel.basic_consume(queue_name, no_wait=False, timeout=self.RABBIT_TIMEOUT)
            # amqp and channels are auto deleted by test case
        self.loop.run_until_complete(go())

    def test_not_exclusive(self):
        @asyncio.coroutine
        def go():
            full_queue_name = self.full_queue_name('q')
            # create a non-exclusive queue
            yield from self.queue_declare('q', exclusive=False)
            # consume it
            yield from self.channel.basic_consume(full_queue_name, no_wait=False, timeout=self.RABBIT_TIMEOUT)
            # create an other amqp connection
            amqp2 = yield from self.create_amqp()
            channel = yield from self.create_channel(amqp=amqp2)
            # assert that this connection can connect to the queue
            yield from channel.basic_consume(full_queue_name, no_wait=False, timeout=self.RABBIT_TIMEOUT)
        self.loop.run_until_complete(go())

    def test_passive(self):
        @asyncio.coroutine
        def go():
            full_queue_name = self.full_queue_name('q')
            yield from self.safe_queue_delete('q')
            # ask for non-existing queue
            channel = yield from self.create_channel()
            with self.assertRaises(exceptions.ChannelClosed):
                yield from channel.queue_declare(full_queue_name, passive=True)
            # create queue
            yield from self.queue_declare('q')
            # get info
            channel = yield from self.create_channel()
            frame = yield from channel.queue_declare(full_queue_name, passive=True)
            self.assertEqual(full_queue_name, frame.arguments['queue'])
        self.loop.run_until_complete(go())