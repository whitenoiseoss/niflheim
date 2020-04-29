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

class EventFactory():
    """
    This will be responsible for creating Events of various types.
    """

    @staticmethod
    def create(etype, **data):
        etype = etype.upper()
        return Event(etype, data)

class EventListener():
    """
    EventListener could be used in Observer or PubSub implementations.
    It will match events that an observer is listening for to Python
    methods and fire them when appropriate.
    """

    def __init__(self, owner=None):
        self.owner = owner
        self.publishers = set()
        self.listeners = dict()
        super(EventListener, self).__init__()

    def on_notify(self, event):
        query = event.type.upper()

        # inject self into the event data if not
        # present
        if "self" not in event.data.keys():
            event.data["self"] = self.owner

        # now send event to listeners
        if query in self.listeners:
            self.listeners[query](event.data)

    def on_destroy(self):
        for p in self.publishers:
            p.remove_event_listener(self)

        self.publishers = []

    def add_event_listener(self, etype, func):
        if etype in self.listeners:
            # TODO: better error handling here
            return False
        else:
            self.listeners[etype] = func
    on = add_event_listener

    def remove_event_listener(self, etype):
        try:
            del(self.listeners[etype])
        except KeyError:
            pass
    off = remove_event_listener

    def add_publisher(self, publisher):
        self.publishers.add(publisher)

    def remove_publisher(self, publisher):
        self.publishers.remove(publisher)

    def all(self):
        return self.listeners

class EventPublisher():
    """
    EventPublisher could be used in Observer or PubSub implementations.
    It will emite events to listeners, either directly or through a topic.

    A topic and an observer should be able to equally present themselves as
    a listener/observer. EventPublisher does not care what the observer is.
    """

    def __init__(self):
        self.subscribers = set()
        super(EventPublisher, self).__init__()

    def notify(self, event, topic=None):
        if topic:
            topic.on_notify(event)
        else:
            for l in self.subscribers:
                l.on_notify(event)
    emit = notify

    def add_subscriber(self, subscriber):
        self.subscribers.add(subscriber)
        subscriber.add_event_publisher(self)

    def remove_subscriber(self, subscriber):
        self.subscribers.remove(subscriber)
        subscriber.remove_event_publisher(self)

class EventTopic(EventListener, EventPublisher):
    """
    EventTopics are both listeners and publishers with slightly modified
    behavior.

    An EventStream will organize them. You may want to avoid creating
    EventTopics independently, and stick to creating them with EventStream.
    """

    def __init__(self, name):
        self.name = name
        super(EventTopic, self).__init__()

class EventStream():
    """
    EventStream will likely become a global Script. This keeps track of all topics,
    to act as an event streamer (like Kafka or similar). This will allow you to
    look up and notify topics by name.
    """

    def __init__(self):
        self.topics = dict()

    def create(self, topic):
        if topic in self.topics:
            raise EventException(
                "EventTopic already exists: {topic}")
        else:
            new_topic = EventTopic(topic)
            self.topics[new_topic.name] = new_topic
            return new_topic

    def add(self, topic):
        if topic.name in self.topics:
            raise EventException(
                "EventTopic already exists: {topic.name}")
        else:
            self.topics[topic.name] = topic
            return True

    def get(self, topic):
        if topic in self.topics:
            return self.topics[topic]
        else:
            return None

    def notify(self, event, topic):
        topic = self.get(topic)
        if topic:
            topic.notify(event)

    def broadcast(self, event):
        raise NotImplementedError

    def multicast(self, event, topics):
        raise NotImplementedError

    def remove(self, topic):
        try:
            del(self.topics[topic])
        except KeyError:
            pass

    @property
    def len(self):
        return len(self.topics)

    @property
    def length(self):
        return len(self.topics)