import json
import os, sys
import uuid
from ...base.events import EventListener
from collections import namedtuple
from functools import wraps


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
        magnitude (int): Strength of Effect
        trait (str): Trait (Stat, Skill, etc) that is affected
        refreshable (bool): Whether or not a second cast will refresh
        stackable (bool): Multiple applications are allowed
        stacks (int): How many stacks currently present
        unique (bool): Only one of type/name can exist
        interval (int): Seconds between recurring effects
        ticks (int): Amount of times Effect applies over time
        commit (func): Method gets assigned here on implementation
    """

    def __init__(self, metadata, name, type, trait, magnitude=0,
                 refreshable=False, stackable=False, stacks=1, 
                 unique=False, interval=0, ticks=1):
        self.metadata = metadata
        if 'description' not in metadata:
            raise EffectException(
                "Required key not found in metadata: 'description'")
        self.name = name
        self.type = type
        self.magnitude = magnitude
        self.trait = trait
        self.refreshable = refreshable
        self.stackable = stackable
        self.stacks = stacks
        self.unique = unique
        self.interval = interval
        self.ticks = ticks
        self.commit = None

    def __str__(self):
        return f"{self.name} ({self.type}): {self.metadata['description']}"

    def __call__(self):
        self.commit(self)

    def for_trait(self, trait):
        self.trait = trait
        return self

class EffectFactory():
    """
    This will be responsible for creating Effects of various types.
    """
    repo = None

    @staticmethod
    def create(name):
        if EffectFactory.repo.db[name]:
            e = Effect(**EffectFactory.repo.db[name].data)
            e.commit = EffectFactory.repo.db[name].func
            return e
        else:
            raise EffectException(
                "Tried to create invalid Effect: {name}")

EffectRepositoryRow = namedtuple('EffectRepositoryRow', ['data', 'func'])

class EffectRepository():
    """
    This will load Effect data from JSON files found in ./effects.json
    TODO: Future versions should have a pluggable JSON file to be read from

    This also handles matching Effects to their method implementations,
    as well as making the database searchable.
    """

    def __init__(self):
        self.data = str()
        self.db = dict()
        self.load()
        for effect in self.data:
            ename = effect["name"]
            if ename in self.db.keys():
                raise EffectException(
                    "Duplicate Effect name in effects.json: {ename}")
            self.db[ename] = EffectRepositoryRow(effect, None)

    def load(self):
        dirname, _ = os.path.split(os.path.abspath(__file__))
        with open(os.path.join(dirname, 'effects.json')) as effects:
            self.data = json.load(effects)
    # alias reload to load method
    reload = load

    @property
    def count(self):
        return len(self.data)

    def add_effect_implementation(self, name, func):
        try:
            row = self.db[name]
            print(row)
        except KeyError:
            raise EffectException(
                f"Tried to implement unknown Effect: {name}")

        if row.func == None:
            self.db[name] = row._replace(func=func)
        else:
            raise EffectException(
                f"Unable to redefine Effect: {name}")

    def implement(self, name):
        @wraps(self, name)
        def decorator(effect_func):
            self.add_effect_implementation(name, effect_func)
            return effect_func

        return decorator

    def where(self, **search):
        """
        This method will search through self.data to enable finding Effects
        by type, name, etc.

        TODO: Implement
        """
        raise NotImplementedError
