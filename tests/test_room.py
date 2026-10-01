"""Room: stream ownership, event fan-out, queue discipline."""

import asyncio
import base64
import unittest

from voice_bridge.room import Room, StreamTakenError, _QUEUE_MAX


def run(coro):
    return asyncio.run(coro)


class OwnershipTests(unittest.TestCase):
    def test_one_stream_at_a_time(self):
        async def go():
            room = Room()
            await room.attach_stream("owner-a")
            with self.assertRaises(StreamTakenError):
                await room.attach_stream("owner-b")

        run(go())

    def test_detach_frees_the_slot(self):
        async def go():
            room = Room()
            first = await room.attach_stream("owner-a")
            await room.detach_stream(first)
            second = await room.attach_stream("owner-b")
            self.assertEqual(second.owner, "owner-b")

        run(go())

    def test_status_reflects_stream(self):
        async def go():
            room = Room()
            self.assertIsNone(room.status()["stream_owner"])
            await room.attach_stream("owner-a")
            self.assertEqual(room.status()["stream_owner"], "owner-a")

        run(go())


class FanOutTests(unittest.TestCase):
    def test_page_audio_becomes_stereo_consumer_event(self):
        async def go():
            room = Room()
            stream = await room.attach_stream("owner-a")
            room.page_audio(b"\x01\x00")  # one mono sample
            event = stream.events.get_nowait()
            self.assertEqual(event["type"], "audio")
            self.assertEqual(event["user_id"], "page")
            self.assertEqual(base64.b64decode(event["pcm"]), b"\x01\x00\x01\x00")

        run(go())

    def test_audio_dropped_without_consumer(self):
        room = Room()
        room.page_audio(b"\x01\x00")  # no stream attached — must not raise

    def test_press_release_become_speaking_events(self):
        async def go():
            room = Room()
            stream = await room.attach_stream("owner-a")
            room.ptt.press()
            room.ptt.release()
            first = stream.events.get_nowait()
            second = stream.events.get_nowait()
            self.assertEqual(first, {"type": "speaking", "user_id": "page", "state": "started"})
            self.assertEqual(second, {"type": "speaking", "user_id": "page", "state": "stopped"})

        run(go())

    def test_consumer_audio_reaches_pages_as_mono(self):
        room = Room()
        queue: asyncio.Queue[bytes] = asyncio.Queue()
        room.add_page(queue)
        room.consumer_audio(b"\x01\x00\x09\x00\x02\x00\x08\x00")
        self.assertEqual(queue.get_nowait(), b"\x01\x00\x02\x00")

    def test_consumer_audio_silently_dropped_without_pages(self):
        Room().consumer_audio(b"\x01\x00\x01\x00")  # must not raise


class QueueDisciplineTests(unittest.TestCase):
    def test_event_queue_drops_oldest_on_overload(self):
        async def go():
            room = Room()
            stream = await room.attach_stream("owner-a")
            for _ in range(_QUEUE_MAX + 50):
                room.ptt.press()
                room.ptt.release()
            self.assertEqual(stream.events.qsize(), _QUEUE_MAX)

        run(go())

    def test_page_queue_drops_oldest_on_overload(self):
        room = Room()
        queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=10)
        room.add_page(queue)
        for i in range(20):
            room.consumer_audio(bytes([i, 0, i, 0]))
        self.assertEqual(queue.qsize(), 10)
        self.assertEqual(queue.get_nowait(), bytes([10, 0]))  # oldest dropped


if __name__ == "__main__":
    unittest.main()
