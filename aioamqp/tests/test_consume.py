
import asyncio
import unittest

from . import testcase
from . import testing
from .. import exceptions


class ConsumeTestCase(testcase.RabbitTestCase, unittest.TestCase):

    _multiprocess_can_split_ = True


    def setUp(self):
        super().setUp()
        self.consume_future = asyncio.Future()

    @asyncio.coroutine
    def callback(self, consumer_tag, deliver_tag, message):
        self.consume_future.set_result((consumer_tag, deliver_tag, message))

    @asyncio.coroutine
    def get_callback_result(self):
        yield from self.consume_future
        result = self.consume_future.result()
        self.consume_future = asyncio.Future()
        return result


    def test_wrong_callback_argument(self):

        def badcallback():
            pass

        yield from self.channel.queue_declare("q", exclusive=True, no_wait=False)
        yield from self.channel.exchange_declare("e", "fanout")
        yield from self.channel.queue_bind("q", "e", routing_key='')

        # get a different channel
        channel = yield from self.create_channel()

        # publish
        yield from channel.publish("coucou", "e", routing_key='',)

        # assert there is a message to consume
        queues = yield from self.list_queues()
        self.assertIn("q", queues)
        self.assertEqual(1, queues["q"]['messages'])

        yield from asyncio.sleep(2)
        # start consume
        with self.assertRaises(exceptions.ConfigurationError):
            yield from channel.basic_consume("q", callback=badcallback)

    @testing.coroutine
    def test_consume(self):
        # declare
        yield from self.channel.queue_declare("q", exclusive=True, no_wait=False)
        yield from self.channel.exchange_declare("e", "fanout")
        yield from self.channel.queue_bind("q", "e", routing_key='')

        # get a different channel
        channel = yield from self.create_channel()

        # publish
        yield from channel.publish("coucou", "e", routing_key='',)

        # assert there is a message to consume
        queues = yield from self.list_queues()
        self.assertIn("q", queues)
        self.assertEqual(1, queues["q"]['messages'])

        yield from asyncio.sleep(2)
        # start consume
        yield from channel.basic_consume("q", callback=self.callback)
        # required ?
        yield from asyncio.sleep(2)

        self.assertTrue(self.consume_future.done())
        # get one
        consumer_tag, delivery_tag, message = yield from self.get_callback_result()
        self.assertIsNotNone(consumer_tag)
        self.assertIsNotNone(delivery_tag)
        self.assertEqual(b"coucou", message)

    @testing.coroutine
    def test_big_consume(self):
        # declare
        yield from self.channel.queue_declare("q", exclusive=True, no_wait=False)
        yield from self.channel.exchange_declare("e", "fanout")
        yield from self.channel.queue_bind("q", "e", routing_key='')


        # get a different channel
        channel = yield from self.create_channel()

        # publish
        yield from channel.publish("a"*1000000, "e", routing_key='',)

        # assert there is a message to consume
        queues = yield from self.list_queues()

        self.assertIn("q", queues)
        self.assertEqual(1, queues["q"]['messages'])

        # start consume
        yield from channel.basic_consume("q", callback=self.callback)

        yield from asyncio.sleep(1)

        self.assertTrue(self.consume_future.done())
        # get one
        consumer_tag, delivery_tag, message = yield from self.get_callback_result()
        self.assertIsNotNone(consumer_tag)
        self.assertIsNotNone(delivery_tag)
        self.assertEqual(b"a"*1000000, message)

    @testing.coroutine
    def test_consume_multiple_queues(self):
        yield from self.channel.queue_declare("q1", exclusive=True, no_wait=False)
        yield from self.channel.queue_declare("q2", exclusive=True, no_wait=False)
        yield from self.channel.exchange_declare("e", "direct")
        yield from self.channel.queue_bind("q1", "e", routing_key="q1")
        yield from self.channel.queue_bind("q2", "e", routing_key="q2")

        # get a different channel
        channel = yield from self.create_channel()

        q1_future = asyncio.Future()

        @asyncio.coroutine
        def q1_callback(consumer_tag, deliver_tag, message):
            q1_future.set_result((consumer_tag, deliver_tag, message))

        q2_future = asyncio.Future()

        @asyncio.coroutine
        def q2_callback(consumer_tag, deliver_tag, message):
            q2_future.set_result((consumer_tag, deliver_tag, message))

        # start consumers
        result = yield from channel.basic_consume("q1", callback=q1_callback)
        ctag_q1 = result['consumer_tag']
        result = yield from channel.basic_consume("q2", callback=q2_callback)
        ctag_q2 = result['consumer_tag']

        # put message in q1
        yield from channel.publish("coucou1", "e", "q1")

        # get it
        consumer_tag, delivery_tag, payload = yield from q1_future
        self.assertEqual(ctag_q1, consumer_tag)
        self.assertIsNotNone(delivery_tag)
        self.assertEqual(b"coucou1", payload)

        # put message in q2
        yield from channel.publish("coucou2", "e", "q2")

        # get it
        consumer_tag, delivery_tag, payload = yield from q2_future
        self.assertEqual(ctag_q2, consumer_tag)
        self.assertEqual(b"coucou2", payload)

    @testing.coroutine
    def test_duplicate_consumer_tag(self):
        yield from self.channel.queue_declare("q1", exclusive=True, no_wait=False)
        yield from self.channel.queue_declare("q2", exclusive=True, no_wait=False)
        yield from self.channel.basic_consume("q1", consumer_tag='tag', callback=self.callback)

        with self.assertRaises(exceptions.ChannelClosed) as cm:
            yield from self.channel.basic_consume("q2", consumer_tag='tag', callback=self.callback)

        self.assertEqual(cm.exception.code, 530)

    @testing.coroutine
    def test_consume_callaback_synced(self):
        # declare
        yield from self.channel.queue_declare("q", exclusive=True, no_wait=False)
        yield from self.channel.exchange_declare("e", "fanout")
        yield from self.channel.queue_bind("q", "e", routing_key='')

        # get a different channel
        channel = yield from self.create_channel()

        # publish
        yield from channel.publish("coucou", "e", routing_key='',)

        # assert there is a message to consume
        queues = yield from self.list_queues()
        self.assertIn("q", queues)
        self.assertEqual(1, queues["q"]['messages'])


        sync_future = asyncio.Future()
        @asyncio.coroutine
        def callback(consumer_tag, deliver_tag, message):
            self.assertTrue(sync_future.done())
            pass

        result = yield from channel.basic_consume("q", callback=callback)
        sync_future.set_result(True)
