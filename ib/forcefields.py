import abc
from typing import List

from openff.models.models import DefaultModel
from openff.toolkit import ForceField as OpenFFForceField
from openmm.app import ForceField as OpenMMForceField


class ForceFieldProvider(DefaultModel, abc.ABC):
    identifier: str

    @classmethod
    @abc.abstractmethod
    def allowed_sources(cls):
        raise NotImplementedError()

    @abc.abstractmethod
    def to_object(self):
        raise NotImplementedError()


class SMIRNOFFForceFieldProvider(ForceFieldProvider):
    identifier: str = "smirnoff"
    # This could just be a str ... trust that it will be a well-formed
    # input and parse it into an object according to some assumptions ...
    forcefield: OpenFFForceField

    @classmethod
    def allowed_sources(cls) -> List:
        return [OpenFFForceField]

    def to_object(self):
        return self.forcefield


class GAFFForceFieldProvider(ForceFieldProvider):
    identifier: str = "gaff"
    forcefield: OpenMMForceField

    @classmethod
    def allowed_sources(cls) -> List:
        return [OpenMMForceField]

    def to_object(self):
        return self.forcefield
