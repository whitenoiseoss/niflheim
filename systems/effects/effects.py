import json
import os, sys
import uuid
from ...base.events import EventListener, EventTopic, EventFactory
from collections import namedtuple, deque, OrderedDict
from functools import wraps, partial

from evennia import DefaultScript


class EffectException(Exception):
    """
    Base exception class raised by `Effect` objects.

    Args:
        msg (str): informative error message
    """

    def __init__(self, msg):
        self.msg = msg

class Effect():
    """
    An Effect is a collection of data that also listens for events, so
    it knows if it has been refreshed or applied again or dispelled.

    Args:
        name (str): Name of the Effect
        type (str): Type of the Effect
        power (int): Strength of Effect
        trait (str): Trait (Stat, Skill, etc) that is affected
        refreshable (bool): Whether or not a second cast will refresh
        stackable (bool): Multiple applications are allowed
        stacks (int): How many stacks currently present
        unique (bool): Only one of type/name can exist
        interval (int): Seconds between recurring effects
        ticks (int): Amount of times Effect applies over time
        commit (func): Method gets assigned here on implementation
    """

    def __init__(self, metadata, name, type, trait, power=0,
                 refreshable=False, stackable=False, stacks=1, 
                 unique=False, interval=0, ticks=1):
        self.metadata = metadata
        if 'description' not in metadata:
            raise EffectException(
                "Required key not found in metadata: 'description'")
        self.name = name
        self.type = type
        self.power = power
        self.trait = trait
        self.refreshable = refreshable
        self.stackable = stackable
        self.stacks = stacks
        self.unique = unique
        self.interval = interval
        self.ticks = ticks
        self.commit = None
        self.events = EventListener(self)

    def __str__(self):
        return f"{self.name} ({self.type}): {self.metadata['description']}"

    def __call__(self, **data):
        self.commit(self, data)

    def for_trait(self, trait):
        self.trait = trait
        return self

    def with_power(self, power):
        self.power = power
        return self

class EffectFactory():
    """
    This will be responsible for creating Effects of various types.
    """

    repo = None

    @staticmethod
    def create(name):
        row = EffectFactory.repo.db[name]

        if row:
            # build the Effect object
            e = Effect(**row.data)
            e.commit = row.func

            # set up events on the Effect
            if row.events:
                for event, func in row.events.items():
                    e.events.add_event_listener(event, func)

            # done
            return e
        else:
            raise EffectException(
                "Tried to create invalid Effect: {name}")

class EffectHandler():
    """
    This is an Abstract Base Class that will be re-implemented on
    various types of objects. It will provide the basis for how
    Effects are added/removed to/from objects in the game.
    """

    def __init__(self, obj):
        self._dict = OrderedDict()
        self.obj = obj
        self.topic = EventTopic(f"{self.obj.name}-EffectHandler")
        self.prioritized = False # TODO: implement optional prioritization

    def add(self, effect, priority=0, **data):
        # index effects by type
        idx = effect.type
        # if the type is not in here, we create
        # the entry for it
        if idx not in self._dict:
            if effect.unique:
                self._dict[idx] = deque([], 1)
            else:
                self._dict[idx] = deque()

        # if it IS already in, we have several
        # checks to do
        if idx in self._dict:
            # stackable doesn't depend on or decide anything, so we can safely do it
            # first
            if effect.stackable:
                # TODO: Implement a _stack_effect to copy certain values over
                # to new effect
                pass
            if effect.unique:
                if effect.refreshable:
                    # TODO: Implement a _refresh_effect to copy certain values over
                    # to new effect, that way stacks would not be lost on refresh
                    self._dict[idx].appendleft(effect)
                    self.emit_to(effect, "REFRESHED", data)
                else:
                    return (False, "UNIQUE_NO_REFRESH")
        self._dict[idx].appendleft(effect)
        self.emit_to(effect, "APPLIED", data)

    def remove(self, effect, **data):
        idx = effect.type
        if idx in self._dict:
            self._dict[idx].pop()
            self.emit_to(effect, "REMOVED", data)

    def notify(self, event):
        self.topic.notify(event)

    def emit_to(self, effect, status, data):
        data["self"] = effect
        try:
            source = data["source"]
        except KeyError: 
            source = self.obj

        e = EventFactory.create(status, source=source, target=self.obj, data=data)

        effect.events.on_notify(e)

    def _get_types_by_priority(self, priority):
        rlist = list()
        for idx in self._dict.keys():
            if idx[0] == priority:
                rlist.append(idx[1])
        
        return sorted(rlist)

    def _get_types_by_keyword(self, keyword):
        rlist = list()
        for idx in self._dict.keys():
            if keyword in idx[1]:
                rlist.append(idx)

        return sorted(rlist, key=lambda t: t[1])

    def _sort_dict(self, dictobj):
        current = 0
        sorted_dict = OrderedDict()
        for x in sorted(self._dict.keys(), key=lambda t: t[0]):
            priority = x[0]
            if priority == current:
                for etype in self._get_types_by_priority(priority):
                    sorted_dict[(priority, etype)] = dictobj[(priority, etype)]
                current += 1
            else:
                continue

    @property
    def len(self):
        return len(self._dict)

    @property
    def length(self):
        return len(self._dict)

EffectRepositoryRow = namedtuple('EffectRepositoryRow', ['data', 'func', 'events'])

class EffectRepository():
    """
    This will load Effect data from JSON files found in ./effects.json
    TODO: Future versions should have a pluggable JSON file to be read from

    This also handles matching Effects to their method implementations,
    as well as making the database searchable.
    """
    db = dict()

    def __init__(self):
        self.data = str()
        self.uniques = set()
        self.load()
        for effect in self.data:
            try:
                # convert str -> boolean
                if effect["unique"].lower() == "true":
                    effect["unique"] = True
                    # add it to uniques list if unique
                    self.uniques.add(effect["type"])
                else:
                    effect["unique"] = False
            except KeyError:
                # it's not defined, so assume it's not unique
                # and default to False
                effect["unique"] = False

            # add to effect DB 
            ename = effect["name"]
            if ename in EffectRepository.db.keys():
                raise EffectException(
                    "Duplicate Effect name in effects.json: {ename}")
            EffectRepository.db[ename] = EffectRepositoryRow(effect, None, {})

    def load(self):
        dirname, _ = os.path.split(os.path.abspath(__file__))
        with open(os.path.join(dirname, 'effects.json')) as effects:
            self.data = json.load(effects)
    # alias reload to load method
    # TODO: reload should do more checking to make sure it doesn't crash
    # the MUD on error
    reload = load

    @property
    def count(self):
        return len(self.data)

    def add_effect_implementation(self, name, func):
        try:
            row = EffectRepository.db[name]
        except KeyError:
            raise EffectException(
                f"Tried to implement unknown Effect: {name}")

        if row.func == None:
            EffectRepository.db[name] = row._replace(func=func)
        else:
            raise EffectException(
                f"Unable to redefine Effect: {name}")

    def add_effect_event_implementation(self, name, event, func):
        event = event.upper()

        try:
            row = EffectRepository.db[name]
        except KeyError:
            raise EffectException(
                f"Tried to implement Event for unknown Effect: {name}")

        if event in row.events.keys():
            raise EffectException(
                f"Unable to redefine Effect Event: {name}:{event}")
        else:
            row.events[event] = func
            EffectRepository.db[name] = row._replace(events=row.events)

    def implement(self, name, event={}):
        @wraps(self, name)
        def decorator(effect_func):
            if event:
                self.add_effect_event_implementation(name, event, effect_func)
            else:
                self.add_effect_implementation(name, effect_func)
            return effect_func

        return decorator

    def is_unique(self, etype):
        return etype in self.uniques

    def where(self, **search):
        """
        This method will search through self.data to enable finding Effects
        by type, name, etc.

        TODO: Implement
        """

        raise NotImplementedError
