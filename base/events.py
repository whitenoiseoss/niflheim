from collections import namedtuple


class EventException(Exception):
    """
    Base exception class raised by `Event` objects.

    Args:
        msg (str): informative error message
    """
    def __init__(self, msg):
        self.msg = msg

Event = namedtuple('Event', ['type', 'data'])

class EventListener():
    """
    EventListener could be used in Observer or PubSub implementations.
    It will match events that an observer is listening for to Python
    methods and fire them when appropriate.
    """

    def __init__(self):
        self._publishers = set()
        self.listeners = dict()

    def on_notify(self, event):
        if event.type in self.listeners:
            self.listeners[event.type](event.data)

    def on_destroy(self):
        for p in self._publishers:
            p.remove_event_listener(self)

        self._publishers = []

    def add_listener(self, etype, func):
        if etype in self.listeners:
            # TODO: better error handling here
            return False
        else:
            self.listeners[etype] = func

    def remove_listener(self, etype):
        try:
            del(self.listeners[etype])
        except KeyError:
            pass

    def add_event_publisher(self, publisher):
        self._publishers.add(publisher)

    def remove_event_publisher(self, publisher):
        self._publishers.remove(publisher)

class EventPublisher():
    """
    EventPublisher could be used in Observer or PubSub implementations.
    It will emite events to listeners, either directly or through a topic.

    A topic and an observer should be able to equally present themselves as
    a listener/observer. EventPublisher does not care what the observer is.
    """

    def __init__(self):
        self._listeners = set()

    def notify(self, event, topic=None):
        if topic:
            topic.on_notify(event)
        else:
            for l in self._listeners:
                l.on_notify(event)

    def add_event_listener(self, listener):
        self._listeners.add(listener)
        listener.add_event_publisher(self)

    def remove_event_listener(self, listener):
        self._listeners.remove(listener)
        listener.remove_event_publisher(self)

class EventTopic(EventListener, EventPublisher):
    """
    EventTopics are both listeners and publishers with slightly modified
    behavior.

    An EventStream will organize them.
    """

    def __init__(self, name):
        self.name = name
        super().__init__()

    def on_notify(self, event):
        for l in self._listeners:
            l.on_notify(event)

class EventStream():
    """
    EventStream will likely become a global Script. This keeps track of all topics,
    to act as an event streamer (like Kafka or similar). This would allow you to
    look up topic references by name.
    """

    def __init__(self):
        self.topics = dict()

    def add_topic(self, topic):
        new_topic = EventTopic(topic)
        if new_topic.name in self.topics:
            # TODO: Better error handling
            return False
        else:
            self.topics[new_topic.name] = new_topic
            return True

    def remove_topic(self, topic):
        try:
            del(self.topics[topic])
        except KeyError:
            pass