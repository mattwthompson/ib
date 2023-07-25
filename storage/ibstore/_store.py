import logging
import pathlib
from collections import defaultdict
from contextlib import contextmanager
from typing import ContextManager, Dict, Iterable, List, TypeVar

import numpy
from openff.qcsubmit.results import OptimizationResultCollection
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ibstore._db import (
    DBBase,
    DBMMConformerRecord,
    DBMoleculeRecord,
    DBQMConformerRecord,
)
from ibstore._session import DBSessionManager
from ibstore._types import Pathlike
from ibstore.analysis import DDE
from ibstore.models import MMConformerRecord, MoleculeRecord, QMConformerRecord

LOGGER = logging.getLogger(__name__)

MS = TypeVar("MS", bound="MoleculeStore")


class MoleculeStore:
    def __len__(self):
        with self._get_session() as db:
            return db.db.query(DBMoleculeRecord.mapped_smiles).count()

    def __init__(self, database_path: Pathlike = "molecule-store.sqlite"):
        database_path = pathlib.Path(database_path)
        if not database_path.suffix.lower() == ".sqlite":
            raise NotImplementedError(
                "Only paths to SQLite databases ending in .sqlite "
                f"are supported. Given: {database_path}"
            )

        self.database_url = f"sqlite:///{database_path.resolve()}"
        self.engine = create_engine(self.database_url)
        DBBase.metadata.create_all(self.engine)

        self._sessionmaker = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
        )

        with self._get_session() as db:
            self.db_version = db.check_version()
            self.general_provenance = db.get_general_provenance()
            self.software_provenance = db.get_software_provenance()

    @contextmanager
    def _get_session(self) -> ContextManager[Session]:
        session = self._sessionmaker()
        try:
            yield DBSessionManager(session)
            session.commit()
        except BaseException as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def _set_provenance(
        self,
        general_provenance: Dict[str, str],
        software_provenance: Dict[str, str],
    ):
        """Set the stores provenance information.

        Parameters
        ----------
        general_provenance
            A dictionary storing provenance about the store such as the author,
            when it was generated etc.
        software_provenance
            A dictionary storing the provenance of the software and packages used
            to generate the data in the store.
        """

        with self._get_session() as db:
            db.set_provenance(
                general_provenance=general_provenance,
                software_provenance=software_provenance,
            )
            self.general_provenance = db.get_general_provenance()
            self.software_provenance = db.get_software_provenance()

    def store(
        self,
        records: Iterable[MoleculeRecord],
    ):
        """Store molecules and their computed properties in the data store.

        Parameters
        ----------
        records: Iterable[MoleculeRecord]
            The QCArchive id and record of each molecule to store.
        """
        if isinstance(records, MoleculeRecord):
            records = [records]

        with self._get_session() as db:
            for record in records:
                db.store_molecule_record(record)

    def store_qcarchive(
        self,
        records: Iterable[QMConformerRecord],
    ):
        if isinstance(records, QMConformerRecord):
            records = [records]

        with self._get_session() as db:
            for record in records:
                if db._qm_conformer_already_exists(record.qcarchive_id):
                    continue
                else:
                    db.store_qm_conformer_record(record)

    def store_conformer(
        self,
        records: Iterable[MMConformerRecord],
    ):
        if isinstance(records, MMConformerRecord):
            records = [records]

        with self._get_session() as db:
            for record in records:
                if db._mm_conformer_already_exists(record.qcarchive_id):
                    continue
                else:
                    db.store_mm_conformer_record(record)

    def store_minimized_conformer(
        self,
        records: Iterable[MMConformerRecord],
    ):
        if isinstance(records, MMConformerRecord):
            records = [records]

        with self._get_session() as db:
            for record in records:
                db.store_mm_conformer_record(record)

    def get_smiles(self) -> List[str]:
        """Get the (mapped) smiles of all records in the store."""
        with self._get_session() as db:
            return [
                smiles
                for (smiles,) in db.db.query(DBMoleculeRecord.mapped_smiles).distinct()
            ]

    def get_inchi_keys(self) -> List[str]:
        """Get the inchi keys of all records in the store."""
        with self._get_session() as db:
            return [
                inchi_key
                for (inchi_key,) in db.db.query(DBMoleculeRecord.inchi_key).distinct()
            ]

    # TODO: Allow by multiple selectors (smiles: list[str])
    def get_molecule_id_by_smiles(self, smiles: str) -> int:
        with self._get_session() as db:
            return [
                id
                for (id,) in db.db.query(DBMoleculeRecord.id)
                .filter_by(mapped_smiles=smiles)
                .all()
            ][0]

    # TODO: Allow by multiple selectors (id: list[int])
    def get_smiles_by_molecule_id(self, id: int) -> str:
        with self._get_session() as db:
            return [
                smiles
                for (smiles,) in db.db.query(DBMoleculeRecord.mapped_smiles)
                .filter_by(id=id)
                .all()
            ][0]

    def get_molecule_id_by_inchi_key(self, inchi_key: str) -> int:
        with self._get_session() as db:
            return [
                id
                for (id,) in db.db.query(DBMoleculeRecord.id)
                .filter_by(inchi_key=inchi_key)
                .all()
            ][0]

    def get_inchi_key_by_molecule_id(self, id: int) -> str:
        with self._get_session() as db:
            return [
                inchi_key
                for (inchi_key,) in db.db.query(DBMoleculeRecord.inchi_key)
                .filter_by(id=id)
                .all()
            ][0]

    def get_qcarchive_ids_by_molecule_id(self, id: int) -> list[str]:
        with self._get_session() as db:
            return [
                qcarchive_id
                for (qcarchive_id,) in db.db.query(DBQMConformerRecord.qcarchive_id)
                .filter_by(parent_id=id)
                .all()
            ]

    # TODO: Allow by multiple selectors (id: list[int])
    def get_qm_energies_by_molecule_id(self, id: int) -> list[float]:
        with self._get_session() as db:
            return [
                energy
                for (energy,) in db.db.query(DBQMConformerRecord.energy)
                .filter_by(parent_id=id)
                .all()
            ]

    # TODO: Allow by multiple selectors (id: list[int])
    def get_mm_energies_by_molecule_id(self, id: int) -> list[float]:
        with self._get_session() as db:
            return [
                energy
                for (energy,) in db.db.query(DBMMConformerRecord.energy)
                .filter_by(parent_id=id)
                .all()
            ]

    @classmethod
    def from_qcsubmit_collection(
        cls,
        collection: OptimizationResultCollection,
        database_name: str,
    ) -> MS:
        from tqdm import tqdm

        store = cls(database_name)

        for qcarchive_record, molecule in tqdm(
            collection.to_records(), desc="Converting records to molecules"
        ):
            # _toolkit_registry_manager could go here

            molecule_record = MoleculeRecord.from_molecule(molecule)

            store.store(molecule_record)

            store.store_qcarchive(
                QMConformerRecord.from_qcarchive_record(
                    molecule_id=store.get_molecule_id_by_smiles(
                        molecule_record.mapped_smiles
                    ),
                    qc_record=qcarchive_record,
                ),
            )

        return store

    def optimize_mm(
        self,
        # force_field,
    ):
        from ibstore._minimize import _minimize_blob

        inchi_keys = self.get_inchi_keys()

        _data = defaultdict(list)

        for inchi_key in inchi_keys:
            molecule_id = self.get_molecule_id_by_inchi_key(inchi_key)

            with self._get_session() as db:
                qm_conformers = [
                    {
                        "qcarchive_id": record.qcarchive_id,
                        "coordinates": record.coordinates,
                    }
                    for record in db.db.query(
                        DBQMConformerRecord,
                    )
                    .filter_by(parent_id=molecule_id)
                    .all()
                ]

                for qm_conformer in qm_conformers:
                    if not db._mm_conformer_already_exists(
                        qm_conformer["qcarchive_id"]
                    ):
                        _data[inchi_key].append(qm_conformer)
                    else:
                        pass

        if len(_data) == 0:
            return

        _minimized_blob = _minimize_blob(_data)

        for inchi_key in _minimized_blob:
            molecule_id = self.get_molecule_id_by_inchi_key(inchi_key)

            for result in _minimized_blob[inchi_key]:
                self.store_conformer(
                    MMConformerRecord(
                        molecule_id=molecule_id,
                        qcarchive_id=result.qcarchive_id,
                        energy=result.energy,
                        coordinates=result.coordinates,
                    )
                )

    def get_dde(
        self,
        # force_field,
    ) -> list[DDE]:
        self.optimize_mm()

        ddes = list()

        for inchi_key in self.get_inchi_keys():
            molecule_id = self.get_molecule_id_by_inchi_key(inchi_key)

            qcarchive_ids = self.get_qcarchive_ids_by_molecule_id(molecule_id)

            if len(qcarchive_ids) == 1:
                # There's only one conformer for this molecule
                # TODO: Quicker way of short-circuiting here
                continue

            qm_energies = self.get_qm_energies_by_molecule_id(molecule_id)
            qm_energies -= numpy.array(qm_energies).min()

            mm_energies = self.get_mm_energies_by_molecule_id(molecule_id)
            mm_energies -= numpy.array(mm_energies).min()

            for qm, mm, id in zip(
                qm_energies,
                mm_energies,
                qcarchive_ids,
            ):
                ddes.append(
                    DDE(
                        qcarchive_id=id,
                        difference=mm - qm,
                    )
                )

        return ddes


def smiles_to_inchi_key(smiles: str) -> str:
    from openff.toolkit import Molecule

    return Molecule.from_smiles(smiles, allow_undefined_stereo=True).to_inchi(
        fixed_hydrogens=True
    )
